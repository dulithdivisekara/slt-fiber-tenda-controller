# Contributing to SLT Fiber Tenda HG7 Controller

Thank you for your interest in contributing to the **SLT Fiber Tenda HG7 Controller** ecosystem! We welcome bug reports, feature enhancements, documentation improvements, and pull requests.

## Development Setup

### 1. Prerequisites
- Linux or macOS (or Windows WSL2)
- Python 3.10+
- Git

### 2. Clone and Setup Environment
```bash
git clone https://github.com/dulithdivisekara/slt-fiber-tenda-controller.git
cd slt-fiber-tenda-controller

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .
```

## Code Quality Standards

### 1. Style Guidelines
- Follow **PEP 8** formatting conventions.
- All code must include descriptive docstrings and type annotations.
- Data structures passed between components must be typed using **Pydantic v2** models (`tenda_controller/models.py`).

### 2. Testing Requirements
Before submitting a pull request, verify that all unit and mock tests pass:
```bash
python3 -m unittest discover -s tests -v
```

When introducing new parsers or API endpoints:
- Add mock HTML fixtures under `tests/` capturing the exact Realtek firmware DOM.
- Write unit tests covering both the happy path and edge cases (e.g. malformed HTML, missing input tags, inactive interfaces).

### 3. Safety Invariants
- **Never** add un-gated mutation endpoints targeting WAN VLANs (`ATM_VC_TBL`), GPON registration (`GPON_PLOAM`), or factory defaults.
- Always implement automatic session cleanup (`logout()`) on newly added workflows to avoid session lockout.
- Never commit credentials, personal phone numbers, or router backups.

## Pull Request Process

1. Create a descriptive feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes and commit using Conventional Commits:
   - `feat: add optical packet error monitoring`
   - `fix: resolve character escaping in rtk_urlencode`
   - `docs: update Super Admin VoIP guide`
3. Push your branch to GitHub and open a Pull Request targeting `main`.
4. Provide a clear PR description detailing:
   - What problem is being solved.
   - What testing was conducted against mock fixtures or live hardware.
