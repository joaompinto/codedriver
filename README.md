# CodeDriver

CodeDriver is a command-line tool that leverages the Claude AI language model to assist with code modifications and analysis. It provides a convenient interface for interacting with Claude, allowing you to request code changes, preview the proposed modifications, and selectively apply them to your project.

## Features

- **Project Analysis**: Get a concise summary of your project's purpose, key features, and main components.
- **Code Modification**: Request code changes by describing the desired modifications in natural language.
- **Change Preview**: View a detailed overview of the proposed changes, including file-by-file diffs.
- **Selective Application**: Apply changes to specific files or the entire project with a simple command.
- **Safety Features**: Automatic backups, preview directories for testing, and patch-based change application ensure a safe modification process.

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

3. Set up your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Usage

1. Navigate to your project directory.

2. Run the `codedriver` command with the desired action:

   - **Project Analysis**:

     ```bash
     codedriver info
     ```

   - **Code Modification**:

     ```bash
     codedriver change "Description of the desired code changes"
     ```

3. Follow the prompts and instructions in the terminal to preview and apply the changes.

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).