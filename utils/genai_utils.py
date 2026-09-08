import ast
import builtins
import json
import re
import requests
import time
import logging

logger = logging.getLogger(__name__)

# NVIDIA NIM chat endpoint (OpenAI-compatible). Free tier, ~40 req/min.
NIM_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_TEXT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"   # best prose, 15-40s
NIM_CODE_MODEL = "meta/muse-glimmer-30b"                     # 3-6s, reliable code fences
# deepseek-v4-pro (178s) and kimi-k3 (timeout) were measured too slow on the free tier.
# First entry is tried first; the next is used if the artifact the mode needs is missing.
# muse-glimmer is ~5x faster but intermittently answers in prose with no
# ```python fence, costing a wasted round-trip, so nemotron leads everywhere and
# muse is the fallback. Follow-ups use muse first: they are short and latency shows.
DEFAULT_MODELS = [NIM_TEXT_MODEL, NIM_CODE_MODEL]
NIM_MODELS = {}


# What "explain it for me" means at each level. The same topic needs a different
# explanation for a first-year student and for someone teaching it.
AUDIENCE = {
    "Beginner": (
        "Audience: a complete beginner.\n"
        "- Open with an everyday analogy before any technical detail.\n"
        # "Define every term" on its own produced a bolded glossary ("- **Algorithm**: ...")
        # and broke the no-markdown rule, so say where the definition goes.
        "- Explain every technical term in plain words the first time it appears, inside the "
        "sentence itself. Do not write a glossary and do not bold the term.\n"
        "- Avoid equations unless one is essential; when you use one, explain every symbol in words.\n"
    ),
    "Intermediate": (
        "Audience: someone who already has basic machine learning vocabulary.\n"
        "- Assume terms like feature, label, loss and gradient are understood.\n"
        "- Include the key equation and explain what each symbol stands for.\n"
        "- Include one worked example with concrete numbers.\n"
    ),
    "Advanced": (
        "Audience: an advanced practitioner.\n"
        "- Be mathematically precise and state the assumptions the method relies on.\n"
        "- Cover failure modes and computational complexity.\n"
        "- Relate the method to neighbouring methods and say when each is preferable.\n"
    ),
}


# How hard the sentences are, which is a separate question from how much theory
# the reader gets. A learner can want the Advanced material and still not want to
# fight through dense academic prose - especially reading in a second language.
# Kept orthogonal to AUDIENCE on purpose: every combination is legitimate.
WORDING = {
    "Simple": (
        "Language: plain and easy to read.\n"
        "- Keep sentences short, about fifteen words, with one idea in each.\n"
        # Same trap as the Beginner audience block: asking for definitions without
        # saying where they go produced a bolded glossary and broke the no-markdown
        # rule, so pin the placement and forbid the formatting here too.
        "- Use everyday words. When a technical word cannot be avoided, say what it "
        "means in ordinary language in the same sentence. Do not write a glossary "
        "and do not bold the term.\n"
        "- Write in the active voice and speak to the reader as \"you\".\n"
        "- Prefer a concrete example of what happens over an abstract description "
        "of what could happen.\n"
    ),
    "Standard": "",
}


# What this tutor will teach, and what it refuses.
#
# Narrow on purpose. A tutor that also answers about history or cooking is a
# worse tutor, because the learner cannot tell which answers are inside its
# competence. The last rule matters as much as the first: most real questions
# never say "machine learning", they say "attention" or "overfitting", and
# refusing those would make the tool useless.
REFUSAL = ("I only cover machine learning - classical ML, deep learning, generative AI "
           "and reinforcement learning. Ask me about one of those and I will help.")

SCOPE = (
    "Scope: artificial intelligence and machine learning only. That includes "
    "classical machine learning, deep learning, generative AI and large language "
    "models, reinforcement learning, computer vision, natural language processing, "
    "and the things these rest on: the maths behind them, how models are trained "
    "and evaluated, datasets and features, and the Python libraries used to build "
    "them such as numpy, pandas, scikit-learn, PyTorch and TensorFlow.\n"
    "If a question is outside that, do not answer it, do not explain why at "
    "length, and do not offer a related answer. Reply with exactly this sentence "
    "and nothing else:\n"
    f"{REFUSAL}\n"
    "Judge the subject, not the wording. Gradient descent, attention, "
    "backpropagation, overfitting, embeddings, tokenisation, a confusion matrix, "
    "a learning rate or a transformer are all in scope even when the question "
    "never uses the words machine learning. General programming, maths or "
    "science questions with no connection to building a model are not.\n"
)


def _chat(api_key, messages, model, max_tokens=4096, temperature=0.7):
    """One NIM chat call. Returns the content string, or None on failure."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.95,
        "max_tokens": max_tokens,
        # Both models are reasoners and otherwise stream their scratchpad into
        # `content`; learners only want the answer.
        "chat_template_kwargs": {"thinking": False},
    }
    for attempt in range(3):
        try:
            response = requests.post(NIM_CHAT_URL, headers=headers, json=payload, timeout=150)
            if response.status_code == 429:
                logger.warning(f"Rate limited by NIM ({model}); retry {attempt + 1}/3")
                time.sleep(10 * (attempt + 1))
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"].get("content") or ""
            return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        except Exception as e:
            logger.error(f"NIM call failed ({model}): {e}")
            return None
    return None


def call_followup(api_key, topic, context, history, question, level="Beginner",
                  wording="Standard"):
    """Answer a follow-up question about material the learner was just shown."""
    system = (
        f"You are a patient tutor. The learner is studying: {topic or 'a computer science topic'}.\n"
        f"{AUDIENCE.get(level, AUDIENCE['Beginner'])}\n"
        f"{WORDING.get(wording, '')}"
        "Here is the material they were shown:\n\n"
        f"{context[:6000]}\n\n"
        "Answer follow-up questions about this material concretely and briefly. "
        "If asked about a specific line of code, quote that line first, then explain it. "
        "Plain text only: no markdown symbols, normal sentence case."
    )
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": str(m["content"])[:4000]}
                 for m in history[-10:]
                 if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": question})
    for model in (NIM_CODE_MODEL, NIM_TEXT_MODEL):   # fast one first
        answer = _chat(api_key, messages, model, max_tokens=1500)
        if answer:
            return answer
    return None

def _wording_rules(wording):
    """The wording block's rules, without its "Language: ..." header line."""
    body = WORDING.get(wording, "")
    lines = [line for line in body.splitlines() if not line.startswith("Language:")]
    return "\n".join(lines).strip("\n")


def _section_explanation(raw):
    """One section's explanation, with any leaked prompt header taken off.

    Belt and braces around the prompt fix above: the model copied "Language:"
    into the middle of its sentences as well as the front, so a header that gets
    through anyway is removed from the text rather than shown to the learner.
    """
    text = re.sub(r"\bLanguage:\s*", "", str(raw or "")).strip()
    text = re.sub(r"\s{2,}", " ", text)
    # Simple wording comes back in lower case often enough to be worth fixing;
    # it sits under a heading, so a lower-case opening reads as a typo.
    return text[:1].upper() + text[1:] if text else text


def _section_title(raw):
    """A heading, from whatever the model called the section.

    Asked for "a short name", models hand back an identifier about half the
    time - `imports_and_data`, `forward_pass_and_gradient_computation`. That
    reads as code in the middle of prose, and the prompt cannot be relied on to
    stop it, so it is undone here instead.
    """
    title = str(raw or "").strip()[:80]
    if "_" in title and " " not in title:
        title = title.replace("_", " ")
    return title[:1].upper() + title[1:] if title else title


def explain_code_sections(api_key, code, topic=None, wording="Standard"):
    """
    Split a generated program into consecutive sections and explain each one.

    Runs as its own call with the finished code in hand, which is far more
    reliable than asking for it in the same response as the code. Returns a list
    of {"title", "code", "explanation"} dicts, or [] if the model does not come
    back with something usable - the prose walkthrough still covers the program
    in that case, so this degrades quietly.

    JSON is used rather than custom markers: it either parses or it does not,
    and every quoted line is checked against the real program so a hallucinated
    snippet cannot be presented as the learner's code.
    """
    numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(code.splitlines()))
    prompt = (
        f"Here is a Python program{' about ' + topic if topic else ''}, with line numbers added:\n\n"
        f"{numbered[:12000]}\n\n"
        "Split this program into 4 to 8 consecutive sections that each do one job "
        "(for example: imports, hyperparameters, environment setup, the training loop, "
        "the update rule, printing results).\n\n"
        "Reply with ONLY a JSON array, no prose before or after it. Each element:\n"
        '{"title": "short name for the section", '
        '"start_line": <first line number>, "end_line": <last line number>, '
        '"explanation": "what this whole section does and why it is needed, 2-4 sentences"}\n\n'
        "Rules: cover the program in order from line 1 to the last line with no gaps and no "
        "overlaps; use the line numbers exactly as shown; do not include the code itself in "
        "the JSON; write explanations in plain sentence case with no markdown.\n"
        # The wording block only ever constrains the "explanation" strings; the JSON
        # shape above is fixed and is not up for rephrasing.
        #
        # Its first line is a header - "Language: plain and easy to read." - and it
        # is dropped here. Left in, the model read it as a pattern to follow and
        # prefixed every sentence it wrote with it: "Language: You import numpy for
        # math. Language: You set a random seed." The sentence above already says
        # what the block is for, so the header earns nothing.
        + (("\nWrite each explanation this way:\n" + _wording_rules(wording))
           if WORDING.get(wording) else "")
    )

    lines = code.splitlines()
    for model in (NIM_TEXT_MODEL, NIM_CODE_MODEL):
        raw = _chat(api_key, [{"role": "user", "content": prompt}], model, max_tokens=3000)
        if not raw:
            continue

        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            logger.warning(f"{model} returned no JSON array for code sections")
            continue
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"{model} returned unparseable section JSON: {e}")
            continue
        if not isinstance(parsed, list):
            continue

        sections = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            try:
                start = int(item["start_line"])
                end = int(item["end_line"])
            except (KeyError, TypeError, ValueError):
                continue
            # Clamp to the real program: the model invents ranges surprisingly often.
            start = max(1, min(start, len(lines)))
            end = max(start, min(end, len(lines)))
            snippet = "\n".join(lines[start - 1:end]).strip("\n")
            title = _section_title(item.get("title"))
            explanation = _section_explanation(item.get("explanation"))
            if not snippet.strip() or not explanation:
                continue
            sections.append({
                "title": title or f"Lines {start}-{end}",
                "code": snippet,
                "explanation": explanation,
                "start_line": start,
                "end_line": end,
            })

        if len(sections) >= 2:
            sections.sort(key=lambda s: s["start_line"])
            return sections
        logger.warning(f"{model} produced too few usable sections; trying next model")

    return []


def generate_quiz(api_key, topic, context="", level="Beginner", wording="Standard"):
    """
    Multiple-choice questions plus key terms for material the learner just read.

    Same contract as explain_code_sections: ask for ONE JSON object, pull it out
    with a regex, validate every field, and drop anything malformed. A quiz whose
    answer key is wrong is worse than no quiz, so a question survives only with
    exactly four options and an answer index that actually points at one of them.

    Returns {"questions": [...], "key_terms": [...]}; both lists empty on failure,
    which the page treats as "the quiz could not be generated".
    """
    prompt = (
        f"Write a short self-check quiz on: {topic}\n"
        f"The learner is at {level} level; pitch the questions there.\n"
        # Applies to the questions, options and explanations - not to the JSON keys.
        + (WORDING[wording] if WORDING.get(wording) else "")
    )
    if context:
        prompt += (
            "\nThey have just read this material, so base the questions on it and, where "
            "code appears, ask what a specific line or parameter does:\n\n"
            f"{context[:6000]}\n"
        )
    prompt += (
        "\nReply with ONLY a JSON object, no prose before or after it:\n"
        '{"questions": [{"question": "...", "options": ["a", "b", "c", "d"], '
        '"answer": <index 0-3 of the correct option>, "explanation": "why that answer is '
        'right, 1-2 sentences"}], '
        '"key_terms": [{"term": "...", "definition": "one sentence"}]}\n\n'
        "Rules: 3 to 6 questions; exactly four options each; mix conceptual questions with "
        "concrete ones; up to 8 key terms; plain sentence case with no markdown."
    )

    # The code model first: quizzes are short and it answers in a few seconds.
    for model in (NIM_CODE_MODEL, NIM_TEXT_MODEL):
        raw = _chat(api_key, [{"role": "user", "content": prompt}], model, max_tokens=2500)
        if not raw:
            continue

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            logger.warning(f"{model} returned no JSON object for the quiz")
            continue
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"{model} returned unparseable quiz JSON: {e}")
            continue
        if not isinstance(parsed, dict):
            continue

        questions = []
        for item in parsed.get("questions") or []:
            if not isinstance(item, dict):
                continue
            options = item.get("options")
            if not isinstance(options, list) or len(options) != 4:
                continue
            options = [str(o).strip() for o in options]
            if not all(options):
                continue
            # bool is an int subclass and would sneak through as index 0/1.
            answer = item.get("answer")
            if isinstance(answer, bool) or not isinstance(answer, int) or not 0 <= answer <= 3:
                continue
            question = str(item.get("question") or "").strip()
            explanation = str(item.get("explanation") or "").strip()
            if not question or not explanation:
                continue
            questions.append({"question": question, "options": options,
                              "answer": answer, "explanation": explanation})
            if len(questions) == 6:
                break

        if not questions:
            logger.warning(f"{model} produced no usable quiz questions; trying next model")
            continue

        key_terms = []
        for item in parsed.get("key_terms") or []:
            if not isinstance(item, dict):
                continue
            term = str(item.get("term") or "").strip()[:60]
            definition = str(item.get("definition") or "").strip()
            if term and definition:
                key_terms.append({"term": term, "definition": definition})
            if len(key_terms) == 8:
                break

        return {"questions": questions, "key_terms": key_terms}

    return {"questions": [], "key_terms": []}


def _code_smells(code):
    """
    Static checks for the two ways generated programs actually broke in testing:
    a call to a function that was never defined (NameError at runtime), and a
    while loop with no exit (the request hangs). Purely an AST inspection - the
    code is never executed here.

    Returns a list of human-readable problems; empty means it looks runnable.
    """
    problems = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"does not parse: {e.msg}"]

    defined = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
            defined.update(a.arg for a in getattr(node.args, "args", []) if hasattr(node, "args"))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                defined.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in defined:
                problems.append(f"calls undefined function '{node.func.id}'")
        elif isinstance(node, ast.While):
            literal_true = isinstance(node.test, ast.Constant) and node.test.value is True
            has_exit = any(isinstance(n, (ast.Break, ast.Return, ast.Raise))
                           for n in ast.walk(node))
            if literal_true and not has_exit:
                problems.append("has a 'while True' loop with no break")
            elif not has_exit and not literal_true:
                # A conditional loop with no escape hatch is how the K-Means
                # sample hung; the prompt asks for a step cap, so require one.
                problems.append("has a while loop with no break or step cap")

    return sorted(set(problems))


def _extract_code(text):
    """
    Pull the program out of a model response.

    Returns (code, remaining_text). Models vary the fence (```python, ```Python,
    ```py, ``` python, CRLF, or bare ```) and the walkthrough sometimes quotes a
    line or two in its own fence, so take the LONGEST block rather than the first
    - the first was yielding 69-character fragments. The block must also parse as
    Python, otherwise it is not something a learner can run.
    """
    # Models sometimes double the fence ("```python" twice, then "```" twice).
    # Left as-is the regex pairs the two openers and captures nothing, so
    # collapse any run of consecutive fence-only lines down to one.
    # Only *identical* neighbours collapse: "```" followed by "```python" is a
    # real close-then-open pair and must be left alone.
    text = re.sub(r"(?m)^(```[ \t]*[a-zA-Z]*)[ \t]*$(?:\r?\n^\1[ \t]*$)+", r"\1", text)

    blocks = list(re.finditer(r"```[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)```",
                              text, re.DOTALL | re.IGNORECASE))
    if not blocks:
        return "", text

    for match in sorted(blocks, key=lambda m: len(m.group(1)), reverse=True):
        code = match.group(1).strip()
        if len(code) < 80:
            continue
        try:
            ast.parse(code)
        except SyntaxError as e:
            logger.warning(f"Discarding code block that does not parse: {e}")
            continue
        rest = text.replace(match.group(0), "")
        # Any remaining fence belongs to a snippet the walkthrough quoted; keep
        # the quoted lines but drop the ``` markers so they don't render raw.
        rest = re.sub(r"^```[ \t]*[a-zA-Z]*[ \t]*$", "", rest, flags=re.MULTILINE)
        return code, rest.strip()

    return "", text


def _strip_markdown(text):
    """
    Remove the two markdown constructs the models still emit despite being told
    not to, so the page never shows raw "**" or "###" to a learner.

    The prompt forbids markdown and mostly that holds, but asking for every term
    to be defined reliably produces a bolded glossary ("- **Algorithm**: ...").
    Instructions did not fix it; deleting the markers does.

    Only markers that sit at a word boundary and wrap non-space text on one line
    are unwrapped, so a Python exponent quoted in a walkthrough survives whether
    it is written "2 ** 3" or "x**2 and y**3". Only headings of two or more
    hashes are stripped, because a single "# " is a code comment.
    """
    text = re.sub(r"(?<![\w*])\*\*(\S(?:[^*\n]*\S)?)\*\*(?![\w*])", r"\1", text)
    return re.sub(r"(?m)^#{2,6}[ \t]+", "", text)


def call_genai(api_key, topic, length, mode, previous_attempts=None, level="Beginner",
               wording="Standard"):
    """
    Call NVIDIA NIM to generate ML learning content

    Args:
        api_key: NVIDIA NIM API key (nvapi-...)
        topic: ML topic to explain
        length: Length of explanation (Brief, Detailed, Comprehensive)
        mode: Output mode (Text explanation, Code with explanation, Audio, Image Explanation)
        previous_attempts: Previous attempts (for retry logic)
        level: Who it is for (Beginner, Intermediate, Advanced) - see AUDIENCE

    Returns:
        Tuple of (briefing, code_content, audio_script, image_prompts)
    """
    audience = AUDIENCE.get(level, AUDIENCE["Beginner"]) + WORDING.get(wording, "")
    scope = SCOPE
    # Enhanced prompt construction
    base_prompt = f"""
You are an expert educational tutor for artificial intelligence and machine learning.

{scope}
Topic: "{topic}"
Required format: {mode}
Explanation depth: {length}

{audience}
Teaching Guidelines:
- Start with a clear learning objective
- Provide structured explanations with examples
- Use appropriate technical depth for the topic
- Include practical applications when relevant
- Ensure accuracy and clarity
- Format output as clean text WITHOUT markdown symbols like #, *, **, etc. The ONLY exception is the ```python code fence, which is REQUIRED whenever code is requested.
- Use plain text formatting with clear paragraphs and line breaks
- For headings, put the heading on its own line in Title Case, followed by a blank line. Never use # symbols.
- For emphasis, use "quotation marks" instead of * or **
- NEVER include stage directions, meta-instructions, or non-content text like "[pause]", "(wait)", "pause here", etc.

"""
    
    code_instruction = ""
    audio_instruction = ""
    image_instruction = ""
    
    if mode == "Code with explanation":
        code_instruction = f"""
- You MUST generate a Python program that demonstrates how {topic} works.
- The Python code itself must be enclosed in a single '```python' and '```' block.
- The program must be complete, runnable end-to-end without edits, and print its results.
- Include helpful comments in the code explaining key steps.
- Re-read the code before finalizing and fix logic errors (for example a reward or update computed on the wrong state, or off-by-one indexing).
- EVERY loop MUST be guaranteed to terminate. A 'while' loop that waits for a goal or for convergence MUST also have a hard step counter that breaks out (for example 'for step in range(100):' or 'if steps > 100: break'). The program must finish in a few seconds.
- Keep the workload small so it runs quickly: at most a few hundred iterations or episodes, and a small dataset.

- AFTER the code block, write a walkthrough using EXACTLY these five headings, each on its own line:

What This Program Does
Two or three sentences on the goal of the program and what it prints.

Packages And Imports
One bullet per imported package, in the form "numpy - what it is, and what it is used for HERE in this program". Name the specific functions used from each package.

Step By Step Walkthrough
Walk through the code in order, section by section. For each section, first quote the actual line or the few lines being explained exactly as they appear in the code, then explain on the next line what they do and why. Write those quoted lines as plain text - do NOT wrap them in backticks or in another code fence. Cover every meaningful section: setup and hyperparameters, data or environment creation, the main loop, the core update or fit step, and the output. Do not skip the central algorithm step.

Key Functions Explained
One entry per function defined or called that matters. Give its name, its parameters, what it returns, and why it is needed.

Things To Try
Two or three concrete edits the learner can make (change a value, print something extra) and what they should expect to see change.

- Use plain text under each heading. Bullets may start with "- ". Do not use markdown symbols like #, * or **.
"""
    
    elif mode == "Audio":
        audio_instruction = """
- Your ENTIRE response is an audio script that will be read aloud verbatim. Do not write a separate written explanation, do not add headings, section titles or bullet points.
- CRITICAL: Write ONLY the actual spoken words - NO stage directions, NO meta-instructions, NO words like "pause", "[pause]", "(pause)", or any other non-spoken text.
- Write as if you are an experienced tutor naturally explaining the topic to a student in a conversation.
- Use natural conversational flow with complete sentences that sound good when spoken aloud.
- Use simple transitions between ideas (like "Now", "Next", "Let me explain", "For example", "This means that").
- Keep sentences clear, not too long, and easy to understand when listening.
- Use an engaging, enthusiastic teaching style that keeps the listener interested.
- Explain concepts step-by-step as if having a one-on-one tutoring session.
- DO NOT include ANY instructions, directions, or notes - only the actual words to be spoken.
"""
    
    elif mode == "Image Explanation":
        image_instruction = f"""
- Additionally, you MUST provide 2-3 text prompts for an image generation AI.
- CRITICAL FORMATTING RULES:
  * Each prompt MUST start on a brand new line with the exact marker 'IMG-PROMPT::' followed by the prompt text.
  * Create prompts for technical diagrams, educational visualizations, and concept illustrations related to {topic}.
  * Focus on clear, educational visual content: diagrams, flowcharts, architectural representations.
  * Use descriptive language for technical accuracy: "neural network architecture diagram", "decision tree visualization", "clustering algorithm illustration".
  * Describe SHAPES, ARROWS and LAYOUT rather than words, because the image model cannot render readable text. Never ask for labels, captions or titles inside the image.
  * Do NOT mention the background or the colour scheme at all - those are added automatically afterwards.
  * Keep each prompt under 40 words.
"""
    
    # Combine all instructions
    prompt = base_prompt + code_instruction + audio_instruction + image_instruction
    
    # Add output format requirements
    prompt += """
Output Requirements:
- Write in normal sentence case. Do NOT write sentences, paragraphs, code comments or headings in all capitals.
- Provide clear, well-structured content
- DO NOT use any markdown formatting symbols (#, *, **, _, etc.), EXCEPT the ```python ... ``` fence around code, which is mandatory when code was requested
- Use plain text with clear paragraph breaks for readability
- Do not add conversational elements like "I hope this helps"
- Focus on educational value and accuracy
- Format headings as Title Case on their own line, not # symbols
- Format emphasis using "quotation marks", not * or **
"""

    # Mode markers go last: earlier in the prompt the formatting rules above
    # outrank them and the model drops the marker entirely.
    if mode == "Code with explanation":
        prompt += """
FINAL REQUIREMENT (do not skip):
Your response MUST contain a Python code block that starts with a line of exactly ```python and ends with a line of exactly ```. Write the code block FIRST, then the five walkthrough sections after it. Without the ```python fence the response is unusable.
"""
    elif mode == "Image Explanation":
        prompt += """
FINAL REQUIREMENT (do not skip):
After the written explanation, output 2-3 image prompts. Each one must start on its own line with the literal marker IMG-PROMPT:: written exactly like that. The marker is mandatory.
"""
    
    # The code walkthrough is long; a 4096 budget left muse-glimmer finishing
    # on 'length' with zero content.
    max_tokens = 7000 if mode == "Code with explanation" else 4096

    models = NIM_MODELS.get(mode, DEFAULT_MODELS)
    for model in models:
        full_response_text = _chat(api_key, [{"role": "user", "content": prompt}], model,
                                   max_tokens=max_tokens)
        if not full_response_text:
            logger.warning(f"{model} returned nothing for mode '{mode}'; trying next model")
            continue

        briefing, code_content, audio_script, image_prompts = full_response_text, "", "", []

        if mode == "Code with explanation":
            code_content, briefing = _extract_code(briefing)
            if not code_content:
                logger.warning(f"{model} returned no usable code block; trying next model")
                continue
            smells = _code_smells(code_content)
            if smells and model != models[-1]:
                # A learner cannot debug this; another model usually can do better.
                logger.warning(f"{model} code has problems ({'; '.join(smells)}); trying next model")
                continue
            if smells:
                logger.warning(f"Shipping code from {model} despite: {'; '.join(smells)}")

        elif mode == "Audio":
            # Asking for explanation + marker + script was unreliable: the model
            # merged the parts and dropped the marker. The response is the script.
            audio_script = briefing

        elif mode == "Image Explanation":
            marker = "IMG-PROMPT::"
            if marker not in briefing:
                logger.warning(f"{model} returned no IMG-PROMPT:: lines; trying next model")
                continue
            first_marker_pos = briefing.find(marker)
            image_prompts = [p.strip() for p in briefing[first_marker_pos:].split(marker) if p.strip()]
            briefing = briefing[:first_marker_pos].strip()

        # Prose only: code_content is already out of `briefing` by this point.
        return _strip_markdown(briefing), code_content, _strip_markdown(audio_script), image_prompts

    logger.error(f"All models failed for mode '{mode}'")
    return None


# ============================== Streaming ==============================
# The chat surface lives or dies on time-to-first-word. A non-streaming call
# leaves a spinner up for 15-90 s; streaming puts words on screen in about a
# second, which is the whole reason the chat interface is worth having.

def stream_chat(api_key, messages, model=None, max_tokens=4096, temperature=0.7,
                thinking=True):
    """Yield ("thinking" | "content", text) as the model produces it.

    ``thinking=False`` sends ``chat_template_kwargs={"thinking": False}``, which
    turns the scratchpad off at the model rather than filtering it here.

    That used to be unusable and the note here said so: on the streaming
    endpoint it suppressed the answer entirely, 1926 characters of reasoning and
    zero of content. Re-measured against both models we call:

        nemotron  + thinking=False   first word 1.6s, no scratchpad, full answer
        nemotron  (reasoning on)     no word in 45s
        muse      + thinking=False   no word in 45s  <- still broken, as noted
        muse      (reasoning on)     no word in 45s

    So it is per-model, and it works on nemotron. It matters because any system
    prompt at all sends these models into minutes of reasoning - the same
    question with no instructions answers in 2.9s - and the chat had reached the
    point where every message hit the thinking budget and errored.

    Reasoning, when it is on, arrives as ``delta.reasoning_content`` and the
    answer as ``delta.content``. They are kept apart so the scratchpad can never
    be mistaken for the lesson.
    """
    model = model or NIM_TEXT_MODEL
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if not thinking:
        payload["chat_template_kwargs"] = {"thinking": False}
    response = requests.post(
        NIM_CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload, stream=True, timeout=(10, 180),
    )
    if response.status_code != 200:
        logger.error("stream_chat %s failed: HTTP %s", model, response.status_code)
        raise RuntimeError(f"model returned {response.status_code}")

    for raw in response.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8", "replace")
        if not line.startswith("data: "):
            continue
        body = line[6:].strip()
        if body == "[DONE]":
            break
        try:
            delta = ((json.loads(body).get("choices") or [{}])[0].get("delta") or {})
        except (ValueError, IndexError, AttributeError):
            continue                       # a malformed frame is not fatal
        if delta.get("reasoning_content"):
            yield "thinking", delta["reasoning_content"]
        if delta.get("content"):
            yield "content", delta["content"]
