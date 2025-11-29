# Contributing to DamaDam Master Bot

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and professional
- Provide constructive feedback
- Report issues responsibly
- Respect privacy and security

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/DDD-Master-Bot.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Install dependencies: `pip install -r requirements.txt`

## Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example config
cp .env.example .env
# Edit .env with your credentials
```

## Making Changes

### Code Style

- Follow PEP 8 guidelines
- Use meaningful variable names
- Add comments for complex logic
- Keep functions focused and small
- Maximum line length: 100 characters

### Commit Messages

- Use clear, descriptive messages
- Start with a verb: "Add", "Fix", "Update", "Remove"
- Reference issues: "Fixes #123"
- Example: `Fix URL cleaning for image posts (#45)`

### Testing

Before submitting:
1. Test with sample profiles
2. Verify Google Sheets integration
3. Check error handling
4. Validate data output

## Submitting Changes

1. Push to your fork
2. Create a Pull Request with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots/logs if applicable
3. Address review feedback
4. Ensure CI/CD passes

## Reporting Issues

### Bug Reports

Include:
- Python version
- OS and browser
- Steps to reproduce
- Expected vs actual behavior
- Error logs
- Screenshots if applicable

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative approaches
- Examples

## Documentation

- Update README for user-facing changes
- Add docstrings to new functions
- Comment complex algorithms
- Update CHANGELOG

## Performance Considerations

- Minimize API calls
- Optimize batch sizes
- Respect rate limits
- Cache when appropriate

## Security

- Never commit credentials
- Use environment variables
- Validate all inputs
- Report security issues privately

## Questions?

- Check existing issues and discussions
- Review documentation
- Ask in pull request comments

Thank you for contributing!
