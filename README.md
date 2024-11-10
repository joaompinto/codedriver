# CodeDriver

CodeDriver is a command-line tool that leverages the Claude AI assistant to analyze and modify code files in your project.

## Key Features

1. **Project Analysis**: Provide a concise summary of the project's purpose, key features, and main components by analyzing the codebase.

2. **Code Modifications**: Generate suggested code changes based on your requirements in the form of a unified diff. Review and apply the changes directly from the CLI.

## Usage

1. Install the required dependencies: `pip install -r requirements.txt`
2. Set up your Anthropic API key as an environment variable: `export ANTHROPIC_API_KEY=your_api_key`
3. Run the CLI:
   - For project analysis: `python -m codedriver info`
   - For code modifications: `python -m codedriver change "description of the changes needed"`

## Development

To contribute to the project, follow these steps:

1. Clone the repository: `git clone https://github.com/your/repo.git`
2. Install development dependencies: `pip install -r requirements-dev.txt`
3. Run tests: `invoke test`
4. Build the package: `python setup.py sdist bdist_wheel`
