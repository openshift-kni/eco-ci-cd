# Slack Notification Script

## Overview

The `send-slack-notification.py` script is a utility for sending automated notifications to Slack channels, primarily designed for CI/CD pipeline failure alerts in the eco-ci-cd project. It supports both templated job failure messages and custom messages.

## Features

- **Job Failure Notifications**: Send structured notifications about failed CI/CD jobs
- **Custom Messages**: Send arbitrary custom messages to Slack channels
- **User Tagging**: Tag specific users in notifications to ensure visibility
- **Jinja2 Templating**: Dynamic message construction using Jinja2 templates
- **Debug Logging**: Optional verbose logging for troubleshooting
- **Simple Integration**: Command-line interface for easy integration with CI/CD pipelines

## Requirements

- Python 3.x
- Dependencies:
  - `requests` - For HTTP communication with Slack API
  - `jinja2` - For message templating

Install dependencies:
```bash
pip install requests jinja2
# or use the requirment file
pip install -r pip.txt
```

## Usage

### Basic Failure Notification

Send a notification about a failed job with release version and link:

```bash
./send-slack-notification.py \
  --webhook-url "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --version "4.15.0" \
  --job-name "deploy-ocp-hybrid" \
  --link "https://jenkins.example.com/job/123"
```

### Notification with User Tags

Tag specific users to notify them about the failure:

```bash
./send-slack-notification.py \
  --webhook-url "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --version "4.15.0" \
  --job-name "deploy-ocp-hybrid" \
  --link "https://jenkins.example.com/job/123" \
  --users user1 user2 user3
```

### Custom Message

Send a custom message instead of the default template:

```bash
./send-slack-notification.py \
  --webhook-url "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --custom-message "Deployment successful for version 4.15.0"
```

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
./send-slack-notification.py \
  --webhook-url "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --version "4.15.0" \
  --link "https://jenkins.example.com/job/123" \
  --debug
```

### Dry Run Mode

Test message formatting without actually sending to Slack:

```bash
./send-slack-notification.py \
  --webhook-url "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --version "4.15.0" \
  --job-name "deploy-ocp-hybrid" \
  --link "https://jenkins.example.com/job/123" \
  --users user1 user2 \
  --dry-run
```

This will print the formatted message to the console without sending it to Slack, useful for testing message formatting before actual deployment.

## Command-Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--webhook-url` | Yes | Slack webhook URL for the target channel |
| `--version` | No | Release version (e.g., "4.15.0") |
| `--job-name` | No | Name of the CI/CD job |
| `--link` | No | URL link to the failed job |
| `--users` | No | Space-separated list of Slack usernames to tag |
| `--custom-message` | No | Custom message to send (overrides template) |
| `--debug` | No | Enable debug logging |
| `--dry-run` | No | Print message to console without sending to Slack |

## Message Template

The default message template structure:

```
Failed Job:
    Release: {version}
    Job: {job_name}
    Link to failed job: {link}

@user1 @user2 @user3
```

## Code Architecture

### Functions

#### `construct_message(args: argparse.Namespace) -> str`
Constructs a formatted message using Jinja2 templating with the provided arguments.

- **Input**: Parsed command-line arguments
- **Output**: Formatted string message
- **Template Fields**: 
  - `version`: Release version
  - `job_name`: Job name (optional)
  - `link`: Link to failed job
  - `users_to_tag`: List of users to mention

#### `log_config(debug: bool) -> None`
Configures the logging system with appropriate log level.

- **Input**: Debug flag (boolean)
- **Output**: None (configures global logger)
- **Levels**: INFO (default) or DEBUG

#### `send_to_slack(args: argparse.Namespace) -> None`
Sends the message to Slack using the webhook URL.

- **Input**: Parsed command-line arguments
- **Output**: None (sends HTTP POST request or prints to console in dry-run mode)
- **Behavior**: 
  - In dry-run mode: prints the message to console without sending
  - In normal mode: sends HTTP POST to Slack webhook
- **Error Handling**: Raises exception on HTTP errors

#### `parse_arguments() -> argparse.Namespace`
Parses and validates command-line arguments.

- **Input**: sys.argv (implicit)
- **Output**: Namespace object with parsed arguments

#### `main() -> None`
Entry point that orchestrates the script execution.

## Slack Webhook Setup

1. Go to your Slack workspace settings
2. Navigate to "Apps" → "Incoming Webhooks"
3. Click "Add New Webhook to Workspace"
4. Select the target channel
5. Copy the generated webhook URL
6. Use the URL with the `--webhook-url` argument

**Security Note**: Store webhook URLs as secrets/environment variables, never hardcode them in scripts or commit them to version control.

## Error Handling

The script will:
- Exit with a non-zero status code if the Slack API returns an error
- Raise `requests.exceptions.HTTPError` for HTTP failures
- Log detailed error information when `--debug` is enabled

## Logging

- **INFO Level** (default): Basic operation information (message sent, using custom message, dry-run mode, etc.)
- **DEBUG Level** (`--debug` flag): Detailed information including:
  - Exact message content being sent
  - HTTP response from Slack
  - Logger initialization details

## Testing and Development

### Dry Run Mode

The `--dry-run` flag is particularly useful for:
- **Testing message formatting** before deploying to production
- **Validating template changes** without spamming Slack channels
- **CI/CD pipeline development** where you want to verify the script executes correctly
- **Debugging message content** by seeing the exact output that would be sent

Example output in dry-run mode:
```
2024-10-29 10:30:45 - INFO - Constructing message to send to Slack
2024-10-29 10:30:45 - INFO - Dry run mode
Failed Job:
    Release: 4.15.0
    Job: deploy-ocp-hybrid
    Link to failed job: https://jenkins.example.com/job/123

@user1 @user2
```

## Limitations

- Does not support Slack's Block Kit formatting (uses simple text messages)
- User tagging uses `@username` format (may not always trigger notifications depending on Slack settings)
- Single channel per invocation (webhook URL determines the channel)

## Related Scripts

- `/scripts/send-slack-notification-bot.py`: Alternative Slack notification implementation with different features

## Contributing

When modifying this script, ensure:
- Maintain backward compatibility with existing CI/CD integrations
- Update this README with any new features or arguments
- Test with debug mode enabled before deployment
- Follow the project's Python coding standards

## License

See the main project [LICENSE](../../../../LICENSE) file.

