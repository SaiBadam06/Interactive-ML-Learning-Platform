# 📘 User Guide

Complete guide to using all features of the ML Learning Assistant.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Text Explanations](#text-explanations)
3. [Code Generation](#code-generation)
4. [Audio Learning](#audio-learning)
5. [Image Visualization](#image-visualization)
6. [Settings](#settings)
7. [Tips & Best Practices](#tips--best-practices)

---

## Getting Started

### First Time Setup

1. **Launch the Application**
   - Start the server: `python app.py`
   - Open browser: `http://localhost:5000`

2. **Configure API Keys**
   - Click "Settings" in navigation
   - Enter your Google Gemini API key
   - Optionally add HuggingFace key
   - Click "Save Settings"

3. **Explore the Homepage**
   - Read feature descriptions
   - Choose your preferred learning mode
   - Click on any feature card to start

---

## Text Explanations

### Overview
Generate comprehensive text-based explanations of any Machine Learning concept.

### How to Use

1. **Navigate to Text Explanation Page**
   - Click "Text" in navigation
   - Or select from homepage

2. **Enter Your Topic**
   - Type any ML concept:
     - "neural networks"
     - "gradient descent"
     - "k-means clustering"
     - "convolutional neural networks"
   - Be specific for better results

3. **Select Explanation Depth**
   - **Brief**: 2-3 paragraphs, quick overview
   - **Detailed**: 5-7 paragraphs, in-depth explanation
   - **Comprehensive**: 10+ paragraphs, complete guide

4. **Generate Content**
   - Click "Generate Explanation"
   - Wait 5-15 seconds
   - View your personalized explanation

5. **Use the Content**
   - **Copy**: Click copy button for clipboard
   - **Download**: Save as .txt file
   - **Read**: Scroll through formatted content

### Example Topics
- Basic: "linear regression", "decision trees"
- Intermediate: "random forest", "gradient boosting"
- Advanced: "transformer architecture", "GANs"

### Tips for Better Results
- Use standard ML terminology
- Be specific: "LSTM networks" vs just "RNN"
- Ask follow-up questions for clarification
- Try different depth levels

---

## Code Generation

### Overview
Generate working Python implementations of ML algorithms with detailed explanations.

### How to Use

1. **Navigate to Code Generation Page**

2. **Enter Algorithm Name**
   - Examples:
     - "linear regression"
     - "k-nearest neighbors"
     - "convolutional neural network"
     - "random forest classifier"

3. **Select Code Complexity**
   - **Brief**: 20-30 lines, simple example
   - **Detailed**: 50-100 lines, full implementation
   - **Comprehensive**: 100+ lines, production-ready

4. **Generate Code**
   - Click "Generate Code"
   - Wait 10-20 seconds
   - View explanation, code, and dependencies

5. **Work with Generated Code**

   **Option A: Copy and Use**
   - Click "Copy Code"
   - Paste into your IDE
   - Install dependencies
   - Run the code

   **Option B: Download**
   - Click "Download"
   - Get .py file
   - Open in your environment
   - Execute as normal Python file

### Running Generated Code

#### Google Colab (Recommended for Beginners)
1. Copy the generated code
2. Click "Open Google Colab" button
3. Create new notebook
4. Paste code in cell
5. Run with Shift + Enter
6. Install dependencies if needed: `!pip install package_name`

#### Local Environment
1. Save code as `algorithm_name.py`
2. Open terminal/command prompt
3. Install dependencies:
   ```bash
   pip install dependency1 dependency2
   ```
4. Run the script:
   ```bash
   python algorithm_name.py
   ```

#### Jupyter Notebook
1. Start Jupyter: `jupyter notebook`
2. Create new notebook
3. Paste code in cells
4. Run cells sequentially
5. Install packages in cells: `!pip install package_name`

### Understanding Dependencies

The app automatically detects required libraries:
- **scikit-learn**: ML algorithms
- **pandas**: Data manipulation
- **numpy**: Numerical computing
- **matplotlib**: Plotting
- **tensorflow/pytorch**: Deep learning

Install all at once:
```bash
pip install scikit-learn pandas numpy matplotlib seaborn
```

### Example Workflows

**Beginner: Learn Linear Regression**
1. Generate code for "linear regression"
2. Select "Brief" complexity
3. Read the explanation first
4. Copy code to Google Colab
5. Run and observe output
6. Modify parameters and re-run

**Intermediate: Build Random Forest**
1. Generate "random forest classifier"
2. Select "Detailed" complexity
3. Download the .py file
4. Install dependencies locally
5. Run on your dataset
6. Analyze results

**Advanced: Implement CNN**
1. Generate "convolutional neural network"
2. Select "Comprehensive" complexity
3. Review the architecture
4. Adapt code to your use case
5. Train on your data

---

## Audio Learning

### Overview
Create AI-generated audio explanations perfect for learning on the go.

### How to Use

1. **Navigate to Audio Learning Page**

2. **Enter Your Topic**
   - Any ML concept works
   - Same topics as text explanations

3. **Select Audio Length**
   - **Brief**: 2-3 minutes
   - **Detailed**: 5-7 minutes
   - **Comprehensive**: 10+ minutes

4. **Generate Audio**
   - Click "Generate Audio"
   - Wait 10-30 seconds (depends on length)
   - Audio player appears automatically

5. **Listen and Learn**
   - **Play in Browser**: Click play button
   - **Download MP3**: Save for offline use
   - **View Script**: Read along with audio

### Best Use Cases

**Commuting**
- Download MP3 to phone
- Listen during drive/transit
- No screen time needed

**Exercise**
- Learn while working out
- Hands-free education
- Multi-task efficiently

**Review**
- Reinforce concepts before exam
- Listen multiple times
- Improve retention

**Accessibility**
- Visual impairment friendly
- Prefer auditory learning
- Screen fatigue relief

### Tips for Audio Learning
- Listen to each lesson 2-3 times
- Take notes while listening
- Pause to reflect on key points
- Combine with text for best results
- Download for offline access

---

## Image Visualization

### Overview
Generate AI-powered diagrams and technical illustrations to understand ML concepts visually.

### How to Use

1. **Navigate to Image Visualization Page**

2. **Enter Concept to Visualize**
   - Architecture-focused topics work best:
     - "neural network architecture"
     - "CNN layers"
     - "transformer attention mechanism"
     - "decision tree structure"

3. **Select Detail Level**
   - **Brief**: Simple diagrams
   - **Detailed**: Comprehensive visuals
   - **Comprehensive**: Technical illustrations

4. **Choose Backend**
   - **Google Gemini**: Fast, free, recommended
   - **Stable Diffusion**: High quality, requires HF key

5. **Generate Images**
   - Click "Generate Images"
   - Wait 15-45 seconds
   - View 2-3 generated images

6. **Use the Images**
   - Right-click to save
   - Use in presentations
   - Reference while studying
   - Share with study groups

### Best Topics for Visualization
- Network architectures
- Algorithm flowcharts
- Data flow diagrams
- Layer structures
- Attention mechanisms
- Tree structures
- Clustering visualizations

### Backend Comparison

| Feature | Google Gemini | Stable Diffusion |
|---------|--------------|------------------|
| Speed | Fast (15-20s) | Slower (30-45s) |
| Quality | Good | Excellent |
| Cost | Free | Free (with API key) |
| Setup | Easy | Requires HF key |
| Best For | Quick diagrams | Detailed illustrations |

### Tips for Better Images
- Be descriptive in your topic
- Include "diagram" or "architecture" in query
- Request specific elements you want shown
- Try both backends for comparison
- Generate multiple times for variations

---

## Settings

### API Key Management

**Saving Keys**
1. Go to Settings page
2. Enter Gemini API key (required)
3. Enter HuggingFace key (optional)
4. Click "Save Settings"
5. Keys stored locally in browser

**Security**
- Keys stored in browser localStorage only
- Never transmitted to our servers
- Can clear anytime
- Encrypted by browser

**Clearing Keys**
1. Click "Clear All Settings"
2. Confirm action
3. Re-enter when needed

### Model Information

Click "View Technical Details" to see:
- Model versions
- Parameters
- Capabilities
- API endpoints

### Privacy Settings

**What We Store**
- API keys (locally in browser)
- Nothing else!

**What We Don't Store**
- Your queries
- Generated content
- Personal information
- Usage data

---

## Tips & Best Practices

### General Tips

1. **Start Simple**
   - Begin with basic concepts
   - Gradually increase complexity
   - Build foundational knowledge

2. **Use Multiple Modes**
   - Read text explanation
   - Study code implementation
   - Listen to audio review
   - View visual diagrams

3. **Be Specific**
   - "Convolutional layers in CNNs" > "CNNs"
   - "Backpropagation algorithm" > "training"
   - "K-means clustering algorithm" > "clustering"

4. **Experiment**
   - Try different depth levels
   - Regenerate for variations
   - Explore related topics
   - Compare approaches

### Learning Strategies

**For Beginners**
1. Start with text explanations
2. Use "Brief" depth initially
3. Progress to code generation
4. Supplement with audio for review

**For Intermediate Learners**
1. Jump to code generation
2. Use "Detailed" complexity
3. Modify and experiment with code
4. Use images for architecture understanding

**For Advanced Users**
1. Use "Comprehensive" depth
2. Focus on implementation details
3. Compare multiple approaches
4. Adapt generated code for projects

### Maximizing Learning

**Daily Routine**
- Morning: Audio lessons during commute
- Afternoon: Code practice and experimentation
- Evening: Text review and visual study

**Project-Based**
1. Choose project goal
2. Generate relevant code
3. Understand with text explanations
4. Visualize architecture
5. Implement and adapt

**Exam Preparation**
1. Generate comprehensive explanations
2. Create audio summaries
3. Review visual diagrams
4. Practice with generated code

### Common Mistakes to Avoid

❌ **Don't:**
- Ask too vague questions
- Skip reading generated content
- Ignore dependencies
- Copy code without understanding
- Use only one learning mode

✅ **Do:**
- Be specific in queries
- Read explanations thoroughly
- Install all dependencies
- Understand before implementing
- Combine multiple modes

---

## Keyboard Shortcuts

- `Ctrl/Cmd + C`: Copy selected content
- `Ctrl/Cmd + S`: Download (when button focused)
- `Tab`: Navigate form fields
- `Enter`: Submit forms
- `Space`: Play/pause audio

---

## FAQ

**Q: How accurate are the explanations?**
A: Generated by state-of-the-art AI, but always verify from official sources.

**Q: Can I use generated code in my projects?**
A: Yes! All generated code is yours to use freely.

**Q: Why is image generation slow?**
A: First request loads the model. Subsequent requests are faster.

**Q: Can I use this offline?**
A: No, requires internet for API calls. But you can download content for offline review.

**Q: Are there usage limits?**
A: Depends on your API keys' quotas. Gemini offers generous free tier.

**Q: Can I request specific code libraries?**
A: Yes, mention the library in your topic: "linear regression using scikit-learn"

---

## Support

Need help?
1. Check this guide
2. Review INSTALLATION.md
3. Read README.md
4. Check troubleshooting section

---

**Happy Learning! 🎓**
