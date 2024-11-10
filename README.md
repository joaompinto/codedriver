# CodeDriver

CodeDriver is an AI-powered tool that helps you modify and analyze code files using natural language prompts. It leverages the Anthropic Claude AI model to understand your requests and generate the necessary code changes or provide insightful analysis.

## Features

- **Code Modification**: Provide a natural language description of the changes you need, and CodeDriver will generate a unified diff with the proposed modifications.
- **Code Analysis**: Get a concise analysis of your codebase, including its main purpose, key features, and main components.
- **Interactive Preview**: Before applying any changes, you can preview the proposed modifications and decide whether to apply them or not.
- **Syntax Highlighting**: Diffs and new files are displayed with syntax highlighting for better readability.

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

### Code Modification

To request code modifications, use the `change` command:

```bash
codedriver change "Description of the changes you need"
```

This will display the proposed changes as a unified diff. You can then choose to apply the changes or not.

### Code Analysis

To get an analysis of your codebase, use the `info` command:

```bash
codedriver info
```

This will provide a concise summary of the main purpose, key features, and main components of your application.

You can also ask a specific question about your codebase:

```bash
codedriver info "What is the purpose of the XYZ component?"
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).
