# nio_key_drop.py
import subprocess
from pathlib import Path

FILE_PATH = Path.home() / ".nio_openai_key"

def run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

# Prompt user with macOS native secure dialog
script = '''
set the_key to text returned of (display dialog "Paste your OpenAI API key:" default answer "" with title "Nio Haus – API Key Setup" with hidden answer)
return the_key
'''

key = run_applescript(script)

if not key.startswith("sk-"):
    run_applescript('display alert "Invalid Key" message "Your OpenAI key must start with sk-."')
    raise SystemExit("Invalid key format.")

# Save key globally
FILE_PATH.write_text(key, encoding='utf-8')

# Confirmation popup
run_applescript(f'display alert "Success" message "Your API key has been saved to:\\n{FILE_PATH}"')

print(f"[*] Key saved to {FILE_PATH}")