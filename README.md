# 🧠 ML Learning Assistant

An intelligent, AI-powered web application for learning Machine Learning concepts through multiple modalities - text explanations, code examples, audio lessons, and visual diagrams.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)

## 🌟 Features

### 📚 Text Explanations
- Get comprehensive, well-structured explanations of any ML concept
- Choose between Brief, Detailed, or Comprehensive depths
- Markdown-formatted content for better readability
- Copy and download explanations

### 💻 Code Generation
- Generate working Python implementations of ML algorithms
- Detailed inline comments for better understanding
- Automatic dependency detection
- Download code as .py files
- Execution guides for Google Colab, local environment, and Jupyter

### 🎧 Audio Learning
- AI-generated audio explanations using Text-to-Speech
- Perfect for learning on the go
- Download MP3 files for offline listening
- Natural, conversational audio scripts

### 🎨 Image Visualization
- AI-powered diagram generation using NVIDIA NIM or FLUX.1-dev
- Technical illustrations and architecture diagrams
- Educational infographics
- Multiple image generation backends

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- NVIDIA NIM API key (required) - [Get it free here](https://build.nvidia.com)
- NVIDIA NIM API key (optional, for FLUX.1-dev) - [Get it here](https://build.nvidia.com)

### Installation

1. **Clone or extract the project**
   ```bash
   cd ml_learning_assistant
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables (optional)**
   ```bash
   # Copy the example env file
   cp .env.example .env
   
   # Edit .env and add your API keys
   # Note: You can also add API keys through the Settings page
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open your browser**
   ```
   Navigate to: http://localhost:5000
   ```

## 📖 Usage Guide

### First Time Setup
1. Navigate to the **Settings** page
2. Enter your NVIDIA NIM API key (required)
3. Optionally add NVIDIA NIM API key for FLUX.1-dev
4. Click "Save Settings" - keys are stored locally in your browser

### Generating Content

#### Text Explanations
1. Go to the **Text Explanation** page
2. Enter any ML topic (e.g., "neural networks", "random forest")
3. Select explanation depth
4. Click "Generate Explanation"
5. Copy or download the generated content

#### Code Examples
1. Go to the **Code Generation** page
2. Enter the ML algorithm you want code for
3. Select complexity level
4. Click "Generate Code"
5. View explanation, code, and dependencies
6. Copy code or download as .py file
7. Follow execution instructions for running the code

#### Audio Lessons
1. Go to the **Audio Learning** page
2. Enter your ML topic
3. Select audio length
4. Click "Generate Audio"
5. Listen directly in browser or download MP3

#### Visual Diagrams
1. Go to the **Image Visualization** page
2. Enter the concept you want visualized
3. Choose backend (NVIDIA NIM recommended for speed)
4. Click "Generate Images"
5. View AI-generated diagrams and illustrations

## 🏗️ Project Structure

```
ml_learning_assistant/
│
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
│
├── utils/                     # Utility modules
│   ├── __init__.py
│   ├── genai_utils.py        # NVIDIA NIM integration
│   ├── audio_utils.py        # Text-to-speech functionality
│   ├── code_executor.py      # Code execution helpers
│   └── image_utils.py        # Image generation utilities
│
├── templates/                 # HTML templates
│   ├── base.html             # Base template
│   ├── index.html            # Homepage
│   ├── text_explanation.html
│   ├── code_generation.html
│   ├── audio_learning.html
│   ├── image_visualization.html
│   ├── settings.html
│   ├── about.html
│   ├── 404.html
│   └── 500.html
│
├── static/                    # Static assets
│   ├── css/
│   │   └── style.css         # Main stylesheet
│   └── js/
│       ├── main.js           # Common JavaScript
│       ├── text_explanation.js
│       ├── code_generation.js
│       ├── audio_learning.js
│       ├── image_visualization.js
│       └── settings.js
│
├── generated_audio/           # Generated audio files
├── generated_code/            # Generated code files
└── uploads/                   # User uploads (if any)
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file based on `.env.example`:

```env
# API Keys (Optional - can be set in Settings page)
NVIDIA_API_KEY=nvapi-your_key_here

# Flask Configuration
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
FLASK_DEBUG=True
```

### API Keys
- **NVIDIA NIM API Key**: Required for all features. Get it from [Google AI Studio](https://build.nvidia.com)
- **NVIDIA NIM API Key**: Optional, only needed if using FLUX.1-dev for image generation

## 🎨 Features in Detail

### Intelligent Content Generation
- Powered by NVIDIA Nemotron 3.5 Lightning 30B for fast, high-quality responses
- Context-aware explanations tailored to your learning level
- Multiple output formats for different learning styles

### Code Quality
- Production-ready Python code with best practices
- Comprehensive inline documentation
- Automatic dependency detection
- Compatible with Google Colab, Jupyter, and local environments

### Audio Quality
- Natural-sounding Text-to-Speech using gTTS
- Conversational, educational tone
- Optimized for clarity and comprehension

### Image Generation
- Two backends: NVIDIA NIM (fast) and FLUX.1-dev (high quality)
- Educational diagram style optimization
- Technical illustrations and architecture visualizations

## 🔒 Privacy & Security

- **Local Storage**: API keys are stored only in your browser's local storage
- **No Data Collection**: We don't collect, store, or share your personal information
- **Secure**: All API communications use HTTPS
- **Open Source**: Review the code yourself

## 🛠️ Troubleshooting

### Common Issues

**Issue**: "Module not found" errors
```bash
# Solution: Reinstall dependencies
pip install -r requirements.txt --upgrade
```

**Issue**: API key errors
```bash
# Solution: Verify your API keys are correct
# Check Settings page or .env file
```

**Issue**: Audio generation fails
```bash
# Solution: Ensure gTTS is installed
pip install gTTS --upgrade
```

**Issue**: Image generation is slow
```bash
# Solution: Use NVIDIA NIM backend instead of NVIDIA NIM
# Or wait for model loading (first request is slower)
```

## 📱 Browser Compatibility

- Chrome/Edge: ✅ Fully supported
- Firefox: ✅ Fully supported
- Safari: ✅ Fully supported
- Mobile browsers: ✅ Responsive design

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **NVIDIA NIM** - For powerful AI text generation
- **Stability AI** - For FLUX.1-dev image generation
- **Flask** - For the excellent web framework
- **gTTS** - For text-to-speech capabilities

## 📧 Support

If you encounter any issues or have questions:
- Check the troubleshooting section above
- Review the code documentation
- Open an issue on GitHub

## 🎓 Educational Use

This tool is designed for educational purposes. Always verify information from multiple sources and consult official documentation for production use.

## 🔮 Future Enhancements

- [ ] Support for more AI models
- [ ] Interactive code execution in browser
- [ ] Quiz generation from topics
- [ ] Progress tracking
- [ ] Multi-language support
- [ ] Video explanation generation
- [ ] Community-shared prompts

---

**Made with ❤️ for the ML learning community**

**Happy Learning! 🚀**
