import jupyter_core.paths as paths
import os
import re

def manage_openrouter_key():
    # Get config directory and file path
    config_dir = paths.jupyter_config_dir()
    config_path = os.path.join(config_dir, "jupyter_notebook_config.py")
    OPENROUTER_KEY = None
    
    # Check if config file exists
    if not os.path.exists(config_path):
        print(f"Config file not found at: {config_path}")
        print("Creating new config file...")
        os.makedirs(config_dir, exist_ok=True)
        open(config_path, 'a').close()
    
    # Read existing config
    with open(config_path, 'r') as file:
        content = file.read()
    
    # Try to extract existing key using regex
    key_match = re.search(r"c\.OpenRouterKey\s*=\s*['\"](.+?)['\"]", content)
    if key_match:
        OPENROUTER_KEY = key_match.group(1)
        print("Found existing OpenRouterKey")
        return OPENROUTER_KEY
    
    # Prompt for key if it doesn't exist
    print("\nOpenRouterKey not found in config.")
    new_key = input("Please enter your OpenRouter API key: ")
    
    # Format the new config entry with proper spacing and comments
    new_config = f"\n\n# OpenRouter API configuration\nc.OpenRouterKey = '{new_key}'\n"
    
    # Append to file
    with open(config_path, 'a') as file:
        file.write(new_config)
    
    print(f"\nSuccessfully added OpenRouterKey to {config_path}")
    OPENROUTER_KEY = new_key
    return OPENROUTER_KEY

if __name__ == "__main__":
    OPENROUTER_KEY = manage_openrouter_key()
    print(f"\nYour OPENROUTER_KEY is: {OPENROUTER_KEY}")
