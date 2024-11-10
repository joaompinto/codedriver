# CodeDriver

CodeDriver is an AI-powered tool that helps you modify and maintain your codebase using natural language prompts. With CodeDriver, you can easily make changes to your code without manually editing files, saving you time and effort.

## Features

- **Natural Language Prompts**: Describe the changes you want to make to your code using plain English.
- **Code Analysis**: Get a high-level analysis of your codebase, including its purpose, key features, and main components.
- **Automatic Code Modification**: CodeDriver generates the necessary code changes based on your prompt and applies them to your files.
- **Diff Preview**: Before applying changes, you can preview the proposed modifications as a unified diff.
- **Selective File Processing**: You can choose to process specific files or scan the entire project directory.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/codedriver.git
cd codedriver
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Set your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_api_key
```

## Usage

### Code Analysis

To get a high-level analysis of your codebase, run:

```bash
python -m codedriver info
```

You can also ask a specific question about your code:

```bash
python -m codedriver info "What is the purpose of the authentication module?"
```

### Code Modification

To modify your code based on a natural language prompt, run:

```bash
python -m codedriver change "Add a new feature to handle user registration"
```

By default, CodeDriver will scan the current directory for code files. You can specify a different directory using the `--path` option:

```bash
python -m codedriver change "Refactor the database layer" --path=/path/to/project
```

You can also process specific files by providing a space-separated list with the `--files` option:

```bash
python -m codedriver change "Fix the bug in the login function" --files="app.py utils.py"
```

Before applying the changes, CodeDriver will show you a preview of the proposed modifications. You can then choose to apply the changes or cancel the operation.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).
