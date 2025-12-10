# 📂 Project Structure

Complete overview of the ML Learning Assistant project structure and file organization.

## Directory Tree

```
ml_learning_assistant/
│
├── 📄 app.py                          # Main Flask application (Entry point)
├── 📄 requirements.txt                # Python dependencies
├── 📄 .env.example                    # Environment variables template
├── 📄 .gitignore                      # Git ignore rules
├── 📄 LICENSE                         # MIT License
│
├── 📄 README.md                       # Project overview and quick start
├── 📄 INSTALLATION.md                 # Detailed installation guide
├── 📄 USER_GUIDE.md                   # Complete user manual
├── 📄 CHANGELOG.md                    # Version history
├── 📄 PROJECT_STRUCTURE.md            # This file
│
├── 🚀 run.sh                          # Startup script (Linux/macOS)
├── 🚀 run.bat                         # Startup script (Windows)
│
├── 📁 utils/                          # Utility modules
│   ├── __init__.py                    # Package initializer
│   ├── genai_utils.py                 # Google Gemini integration
│   ├── audio_utils.py                 # Text-to-speech functionality
│   ├── code_executor.py               # Code execution helpers
│   └── image_utils.py                 # Image generation utilities
│
├── 📁 templates/                      # HTML templates (Jinja2)
│   ├── base.html                      # Base template (navigation, footer)
│   ├── index.html                     # Homepage
│   ├── text_explanation.html          # Text explanation page
│   ├── code_generation.html           # Code generation page
│   ├── audio_learning.html            # Audio learning page
│   ├── image_visualization.html       # Image visualization page
│   ├── settings.html                  # Settings/configuration page
│   ├── about.html                     # About page
│   ├── 404.html                       # Not found error page
│   └── 500.html                       # Server error page
│
├── 📁 static/                         # Static assets
│   ├── 📁 css/
│   │   └── style.css                  # Main stylesheet (responsive)
│   ├── 📁 js/
│   │   ├── main.js                    # Common JavaScript functions
│   │   ├── text_explanation.js        # Text page functionality
│   │   ├── code_generation.js         # Code page functionality
│   │   ├── audio_learning.js          # Audio page functionality
│   │   ├── image_visualization.js     # Image page functionality
│   │   └── settings.js                # Settings page functionality
│   └── 📁 images/                     # (Reserved for future use)
│
├── 📁 generated_audio/                # Generated audio files (MP3)
│   └── .gitkeep                       # Keep directory in git
│
├── 📁 generated_code/                 # Generated code files (Python)
│   └── .gitkeep                       # Keep directory in git
│
└── 📁 uploads/                        # User uploads (if any)
    └── .gitkeep                       # Keep directory in git
```

---

## Core Files

### `app.py`
**Purpose**: Main Flask application
**Key Features**:
- Flask app initialization
- Route definitions
- API endpoints
- Error handlers
- File upload handling

**Routes**:
- `/` - Homepage
- `/text-explanation` - Text page
- `/code-generation` - Code page
- `/audio-learning` - Audio page
- `/image-visualization` - Image page
- `/settings` - Settings page
- `/about` - About page
- `/api/generate-text` - Text generation API
- `/api/generate-code` - Code generation API
- `/api/generate-audio` - Audio generation API
- `/api/generate-images` - Image generation API
- `/api/model-info` - Model information API
- `/api/download-code/<filename>` - Download code files
- `/api/download-audio/<filename>` - Download audio files

---

## Utility Modules (`utils/`)

### `genai_utils.py`
**Purpose**: Google Gemini AI integration
**Functions**:
- `call_genai()` - Main function to call Gemini API
- Prompt construction
- Response parsing
- Error handling and retries

**Key Features**:
- Supports multiple output modes
- Handles rate limiting
- Parses code blocks
- Extracts image prompts
- Extracts audio scripts

### `audio_utils.py`
**Purpose**: Text-to-speech functionality
**Functions**:
- `text_to_audio()` - Convert text to MP3
- `delete_old_audio_files()` - Cleanup old files

**Technology**: Google Text-to-Speech (gTTS)

### `code_executor.py`
**Purpose**: Code-related utilities
**Functions**:
- `detect_dependencies()` - Find required packages
- `save_code_to_file()` - Save code to .py file
- `get_execution_instructions()` - Get run instructions
- `delete_old_code_files()` - Cleanup old files

### `image_utils.py`
**Purpose**: Image generation
**Functions**:
- `generate_images()` - Main image generation
- `_gen_with_gemini()` - Gemini backend
- `_gen_with_hf()` - HuggingFace backend
- `_enhance_educational_prompt()` - Prompt enhancement
- `get_model_info()` - Model information

**Backends**:
- Google Gemini 2.0 Flash (Image Generation)
- Imagen 3.0 (Fallback)
- Stable Diffusion XL (HuggingFace)

---

## Templates (`templates/`)

### `base.html`
**Purpose**: Base template for all pages
**Includes**:
- Navigation bar
- Footer
- Toast notifications
- Loading overlay
- Common CSS/JS imports

**Structure**:
```html
{% block title %}{% endblock %}
{% block extra_css %}{% endblock %}
{% block content %}{% endblock %}
{% block extra_js %}{% endblock %}
```

### Page Templates
All page templates extend `base.html` and include:
- Page header with icon
- Input forms
- Output sections
- Tips/help sections
- Page-specific JavaScript

**Design Principles**:
- Responsive design (mobile-first)
- Consistent layout
- Clear call-to-actions
- Helpful tooltips
- Error handling
- Loading states

---

## Static Assets (`static/`)

### `style.css`
**Purpose**: Main stylesheet
**Features**:
- CSS variables for theming
- Responsive grid system
- Mobile-first approach
- Animations and transitions
- Print styles
- Accessibility features

**Key Sections**:
- Variables and reset
- Navigation
- Hero section
- Cards and forms
- Buttons
- Output sections
- Tips and info sections
- Footer
- Modals and toasts
- Responsive breakpoints

### JavaScript Files

#### `main.js`
**Purpose**: Common utilities
**Functions**:
- `showToast()` - Show notifications
- `showLoading()` - Toggle loading overlay
- `getApiKey()` - Retrieve API keys
- `copyToClipboard()` - Copy text
- `downloadTextFile()` - Download content
- `formatMarkdown()` - Simple markdown parsing

#### Page-Specific JS
Each page has its own JavaScript file that:
- Handles form submissions
- Makes API calls
- Displays results
- Manages UI interactions
- Implements page-specific features

---

## Generated Content Directories

### `generated_audio/`
**Purpose**: Store generated MP3 files
**Naming**: `{topic}_{timestamp}.mp3`
**Cleanup**: Old files deleted after 24 hours

### `generated_code/`
**Purpose**: Store generated Python files
**Naming**: `{topic}_{timestamp}.py`
**Cleanup**: Old files deleted after 24 hours

### `uploads/`
**Purpose**: User file uploads (future feature)
**Currently**: Reserved for future use

---

## Configuration Files

### `requirements.txt`
**Purpose**: Python package dependencies
**Packages**:
- Flask - Web framework
- python-dotenv - Environment variables
- google-generativeai - Gemini API
- google-genai - Gemini SDK
- gTTS - Text-to-speech
- requests - HTTP client
- Pillow - Image processing
- Werkzeug - WSGI utilities

### `.env.example`
**Purpose**: Environment variables template
**Variables**:
- `GEMINI_API_KEY` - Google Gemini API key
- `HF_API_KEY` - HuggingFace API key
- `SECRET_KEY` - Flask secret key
- `FLASK_ENV` - Environment (development/production)
- `FLASK_DEBUG` - Debug mode flag

### `.gitignore`
**Purpose**: Git ignore patterns
**Ignores**:
- Python cache files
- Virtual environments
- Environment files
- Generated content
- IDE files
- Logs and temporary files

---

## Documentation Files

### `README.md`
- Project overview
- Features list
- Quick start guide
- Installation summary
- Basic usage
- License and credits

### `INSTALLATION.md`
- System requirements
- Python installation
- Project setup
- API key configuration
- Troubleshooting
- Advanced configuration

### `USER_GUIDE.md`
- Complete feature documentation
- Step-by-step tutorials
- Best practices
- Tips and tricks
- FAQ section
- Keyboard shortcuts

### `CHANGELOG.md`
- Version history
- Release notes
- Feature additions
- Bug fixes
- Future roadmap

---

## Startup Scripts

### `run.sh` (Linux/macOS)
**Features**:
- Python version check
- Virtual environment creation
- Dependency installation
- .env file setup
- Server startup

### `run.bat` (Windows)
**Features**:
- Same as run.sh but for Windows
- Batch file format
- Windows-specific commands

---

## Data Flow

### Text Generation
1. User enters topic in `text_explanation.html`
2. `text_explanation.js` sends AJAX request
3. `app.py` receives request at `/api/generate-text`
4. `genai_utils.call_genai()` calls Gemini API
5. Response parsed and returned to frontend
6. `text_explanation.js` displays content

### Code Generation
1. User enters algorithm in `code_generation.html`
2. `code_generation.js` sends request
3. `app.py` routes to `/api/generate-code`
4. `genai_utils.call_genai()` generates code
5. `code_executor.detect_dependencies()` finds packages
6. `code_executor.save_code_to_file()` saves file
7. Response with code, deps, and filename returned
8. `code_generation.js` displays all components

### Audio Generation
1. User submits topic in `audio_learning.html`
2. `audio_learning.js` sends request
3. `app.py` routes to `/api/generate-audio`
4. `genai_utils.call_genai()` creates script
5. `audio_utils.text_to_audio()` generates MP3
6. Audio file saved to `generated_audio/`
7. Filename returned to frontend
8. `audio_learning.js` creates audio player

### Image Generation
1. User enters concept in `image_visualization.html`
2. `image_visualization.js` sends request
3. `app.py` routes to `/api/generate-images`
4. `genai_utils.call_genai()` creates prompts
5. `image_utils.generate_images()` creates images
6. Base64-encoded images returned
7. `image_visualization.js` displays gallery

---

## Security Considerations

### API Keys
- Stored in browser localStorage (client-side)
- Transmitted via HTTPS (production)
- Never logged or stored on server
- Can be cleared anytime

### Generated Content
- Files stored temporarily (24 hours)
- Unique filenames prevent collisions
- No user data in filenames
- Automatic cleanup

### Input Validation
- Form validation on frontend
- Server-side validation
- Sanitized inputs
- Error handling

---

## Performance Optimizations

### Frontend
- Minified CSS/JS (production)
- Lazy loading for images
- Efficient DOM manipulation
- Debounced API calls

### Backend
- Efficient file handling
- Proper error handling
- Retry logic for API calls
- Async operations where possible

### API Usage
- Rate limit handling
- Caching where appropriate
- Efficient prompt construction
- Minimal token usage

---

## Deployment Considerations

### Development
- Debug mode enabled
- Detailed error pages
- Hot reloading
- Local file serving

### Production
- Debug mode disabled
- Secure secret key
- HTTPS enforcement
- Error logging
- Performance monitoring
- Load balancing (if needed)
- CDN for static files

---

## Future Enhancements

### Planned Structure Changes
- `tests/` - Unit and integration tests
- `migrations/` - Database migrations
- `static/images/` - UI images and icons
- `docs/` - API documentation
- `scripts/` - Utility scripts
- `config/` - Configuration files

### Planned Features
- User authentication
- Database integration
- API rate limiting
- Content caching
- Advanced analytics
- Multi-language support

---

## File Size Reference

| Component | Approx. Size |
|-----------|--------------|
| Python files | ~50KB |
| HTML templates | ~100KB |
| CSS | ~80KB |
| JavaScript | ~30KB |
| Documentation | ~200KB |
| Total (without dependencies) | ~460KB |
| With dependencies | ~50MB |

---

## Maintenance

### Regular Tasks
- Update dependencies
- Clear old generated files
- Review error logs
- Monitor API usage
- Update documentation

### Backup
- Code repository (Git)
- Configuration files
- Documentation
- User settings (if stored)

---

This structure is designed for:
✅ Easy navigation
✅ Clear separation of concerns
✅ Scalability
✅ Maintainability
✅ Documentation
✅ Testing
✅ Deployment

