import os
import json
import argparse
import logging
import getpass
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class ConfigUtility:
    """Utility for configuring the Notes Digest application."""
    
    DEFAULT_CONFIG = {
        "notes_folder": "./notes_folder",
        "db_path": "notes_digest.db",
        "api_key": "",
        "weekly_digest_day": "Sunday",
        "monthly_digest_day": 1,
        "output_dir": "digests",
        "schedule": {
            "weekly_digest": True,
            "monthly_digest": True,
            "task_list": True,
            "suggested_reading": True
        },
        "processing": {
            "enable_ocr": True,
            "enable_web_fetching": True,
            "max_text_length": 10000,
            "handwriting_threshold": 20  # words per page
        },
        "llm": {
            "model": "claude-3-7-sonnet-20250219",
            "temperature": 0.7,
            "max_tokens": 4000,
            "analysis_depth": "standard"  # [basic, standard, comprehensive]
        }
    }
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from file or create default."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    logger.info(f"Configuration loaded from {self.config_path}")
                    return config
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                logger.info("Using default configuration")
                return self.DEFAULT_CONFIG.copy()
        else:
            logger.info(f"Configuration file not found at {self.config_path}")
            logger.info("Using default configuration")
            return self.DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def interactive_setup(self):
        """Run interactive setup to configure the application."""
        print("\n=== Notes Digest Configuration ===\n")
        
        # Notes folder
        default_notes = self.config.get("notes_folder", self.DEFAULT_CONFIG["notes_folder"])
        notes_folder = input(f"Enter path to notes folder [default: {default_notes}]: ").strip()
        if notes_folder:
            notes_path = Path(notes_folder)
            # Create folder if it doesn't exist
            if not notes_path.exists():
                try:
                    notes_path.mkdir(parents=True)
                    print(f"Created folder: {notes_folder}")
                except Exception as e:
                    print(f"Error creating folder: {e}")
                    notes_folder = default_notes
            self.config["notes_folder"] = notes_folder
        else:
            self.config["notes_folder"] = default_notes
        
        # API Key
        current_key = self.config.get("api_key", "")
        masked_key = "********" if current_key else "not set"
        print(f"Current API key: {masked_key}")
        
        update_key = input("Update API key? (y/n): ").lower().strip()
        if update_key == 'y':
            new_key = getpass.getpass("Enter your API key: ").strip()
            if new_key:
                self.config["api_key"] = new_key
                print("API key updated")
            else:
                print("API key unchanged")
        
        # Output directory
        default_output = self.config.get("output_dir", self.DEFAULT_CONFIG["output_dir"])
        output_dir = input(f"Enter path for output digests [default: {default_output}]: ").strip()
        if output_dir:
            output_path = Path(output_dir)
            # Create folder if it doesn't exist
            if not output_path.exists():
                try:
                    output_path.mkdir(parents=True)
                    print(f"Created folder: {output_dir}")
                except Exception as e:
                    print(f"Error creating folder: {e}")
                    output_dir = default_output
            self.config["output_dir"] = output_dir
        else:
            self.config["output_dir"] = default_output
        
        # Scheduling
        print("\n=== Scheduling Configuration ===")
        
        # Weekly digest scheduling
        default_weekly = self.config.get("schedule", {}).get("weekly_digest", True)
        weekly_enabled = input(f"Enable weekly digest generation? (y/n) [default: {'y' if default_weekly else 'n'}]: ").strip()
        if weekly_enabled:
            weekly_enabled = weekly_enabled.lower() == 'y'
        else:
            weekly_enabled = default_weekly
        
        self.config.setdefault("schedule", {})["weekly_digest"] = weekly_enabled
        
        if weekly_enabled:
            default_day = self.config.get("weekly_digest_day", "Sunday")
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            print("Select day for weekly digest:")
            for i, day in enumerate(days, 1):
                print(f"{i}. {day}")
            
            day_choice = input(f"Enter number [default: {days.index(default_day)+1}]: ").strip()
            if day_choice and day_choice.isdigit() and 1 <= int(day_choice) <= 7:
                self.config["weekly_digest_day"] = days[int(day_choice)-1]
            else:
                self.config["weekly_digest_day"] = default_day
        
        # Monthly digest scheduling
        default_monthly = self.config.get("schedule", {}).get("monthly_digest", True)
        monthly_enabled = input(f"Enable monthly digest generation? (y/n) [default: {'y' if default_monthly else 'n'}]: ").strip()
        if monthly_enabled:
            monthly_enabled = monthly_enabled.lower() == 'y'
        else:
            monthly_enabled = default_monthly
        
        self.config.setdefault("schedule", {})["monthly_digest"] = monthly_enabled
        
        # Task list scheduling
        default_tasks = self.config.get("schedule", {}).get("task_list", True)
        tasks_enabled = input(f"Enable daily task list generation? (y/n) [default: {'y' if default_tasks else 'n'}]: ").strip()
        if tasks_enabled:
            tasks_enabled = tasks_enabled.lower() == 'y'
        else:
            tasks_enabled = default_tasks
        
        self.config.setdefault("schedule", {})["task_list"] = tasks_enabled
        
        # LLM configuration
        print("\n=== LLM Configuration ===")
        
        # Model selection
        default_model = self.config.get("llm", {}).get("model", self.DEFAULT_CONFIG["llm"]["model"])
        models = [
            "claude-3-7-sonnet-20250219",
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20240620"
        ]
        
        print("Select LLM model:")
        for i, model in enumerate(models, 1):
            print(f"{i}. {model}")
        
        model_choice = input(f"Enter number [default: {models.index(default_model)+1 if default_model in models else 1}]: ").strip()
        if model_choice and model_choice.isdigit() and 1 <= int(model_choice) <= len(models):
            selected_model = models[int(model_choice)-1]
        else:
            selected_model = default_model
        
        self.config.setdefault("llm", {})["model"] = selected_model
        
        # Analysis depth
        default_depth = self.config.get("llm", {}).get("analysis_depth", "standard")
        depths = ["basic", "standard", "comprehensive"]
        
        print("\nSelect analysis depth:")
        print("1. Basic - Minimal processing, faster results")
        print("2. Standard - Balanced analysis and performance")
        print("3. Comprehensive - Detailed analysis, higher API usage")
        
        depth_choice = input(f"Enter number [default: {depths.index(default_depth)+1}]: ").strip()
        if depth_choice and depth_choice.isdigit() and 1 <= int(depth_choice) <= 3:
            selected_depth = depths[int(depth_choice)-1]
        else:
            selected_depth = default_depth
        
        self.config.setdefault("llm", {})["analysis_depth"] = selected_depth
        
        # Advanced processing options
        print("\n=== Advanced Processing Options ===")
        
        # OCR
        default_ocr = self.config.get("processing", {}).get("enable_ocr", True)
        ocr_enabled = input(f"Enable OCR for images and PDFs? (y/n) [default: {'y' if default_ocr else 'n'}]: ").strip()
        if ocr_enabled:
            ocr_enabled = ocr_enabled.lower() == 'y'
        else:
            ocr_enabled = default_ocr
        
        self.config.setdefault("processing", {})["enable_ocr"] = ocr_enabled
        
        # Web fetching
        default_web = self.config.get("processing", {}).get("enable_web_fetching", True)
        web_enabled = input(f"Enable fetching content from URLs? (y/n) [default: {'y' if default_web else 'n'}]: ").strip()
        if web_enabled:
            web_enabled = web_enabled.lower() == 'y'
        else:
            web_enabled = default_web
        
        self.config.setdefault("processing", {})["enable_web_fetching"] = web_enabled
        
        # Save configuration
        print("\nSaving configuration...")
        if self.save_config():
            print(f"Configuration saved to {self.config_path}")
            print("\nConfiguration complete! You can now start the application.")
        else:
            print(f"Error saving configuration to {self.config_path}")
    
    def print_config(self):
        """Print the current configuration."""
        print("\n=== Current Configuration ===\n")
        
        # Basic settings
        print("Basic Settings:")
        print(f"  Notes Folder: {self.config.get('notes_folder')}")
        print(f"  Database Path: {self.config.get('db_path')}")
        print(f"  Output Directory: {self.config.get('output_dir')}")
        
        # API key (masked)
        api_key = self.config.get("api_key", "")
        masked_key = "********" if api_key else "not set"
        print(f"  API Key: {masked_key}")
        
        # Schedule settings
        print("\nSchedule Settings:")
        schedule = self.config.get("schedule", {})
        print(f"  Weekly Digest: {'Enabled' if schedule.get('weekly_digest', True) else 'Disabled'}")
        if schedule.get("weekly_digest", True):
            print(f"    Day: {self.config.get('weekly_digest_day', 'Sunday')}")
        
        print(f"  Monthly Digest: {'Enabled' if schedule.get('monthly_digest', True) else 'Disabled'}")
        print(f"  Task List: {'Enabled' if schedule.get('task_list', True) else 'Disabled'}")
        print(f"  Suggested Reading: {'Enabled' if schedule.get('suggested_reading', True) else 'Disabled'}")
        
        # LLM settings
        print("\nLLM Settings:")
        llm = self.config.get("llm", {})
        print(f"  Model: {llm.get('model', 'claude-3-7-sonnet-20250219')}")
        print(f"  Analysis Depth: {llm.get('analysis_depth', 'standard')}")
        print(f"  Temperature: {llm.get('temperature', 0.7)}")
        print(f"  Max Tokens: {llm.get('max_tokens', 4000)}")
        
        # Processing settings
        print("\nProcessing Settings:")
        processing = self.config.get("processing", {})
        print(f"  OCR Enabled: {'Yes' if processing.get('enable_ocr', True) else 'No'}")
        print(f"  Web Fetching Enabled: {'Yes' if processing.get('enable_web_fetching', True) else 'No'}")
        print(f"  Max Text Length: {processing.get('max_text_length', 10000)} characters")
        print(f"  Handwriting Threshold: {processing.get('handwriting_threshold', 20)} words per page")
    
    def validate_config(self):
        """Validate the configuration and fix any issues."""
        # Check required fields
        required_fields = ["notes_folder", "db_path", "output_dir"]
        missing_fields = [field for field in required_fields if field not in self.config]
        
        if missing_fields:
            logger.warning(f"Missing required configuration fields: {', '.join(missing_fields)}")
            for field in missing_fields:
                self.config[field] = self.DEFAULT_CONFIG[field]
        
        # Ensure directories exist
        for dir_field in ["notes_folder", "output_dir"]:
            dir_path = self.config.get(dir_field)
            if dir_path and not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path)
                    logger.info(f"Created directory: {dir_path}")
                except Exception as e:
                    logger.error(f"Error creating directory {dir_path}: {e}")
                    self.config[dir_field] = self.DEFAULT_CONFIG[dir_field]
        
        # Ensure nested dictionaries exist
        for nested_dict in ["schedule", "processing", "llm"]:
            if nested_dict not in self.config:
                self.config[nested_dict] = self.DEFAULT_CONFIG[nested_dict]
        
        # Validate weekly digest day
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if self.config.get("weekly_digest_day") not in valid_days:
            logger.warning(f"Invalid weekly digest day: {self.config.get('weekly_digest_day')}")
            self.config["weekly_digest_day"] = self.DEFAULT_CONFIG["weekly_digest_day"]
        
        # Save validated config
        self.save_config()
        
        return len(missing_fields) == 0
    
    def set_option(self, key, value):
        """Set a configuration option."""
        # Handle nested keys with dot notation
        if '.' in key:
            sections = key.split('.')
            current = self.config
            for section in sections[:-1]:
                if section not in current:
                    current[section] = {}
                current = current[section]
            current[sections[-1]] = value
        else:
            self.config[key] = value
        
        return self.save_config()
    
    def get_option(self, key):
        """Get a configuration option."""
        # Handle nested keys with dot notation
        if '.' in key:
            sections = key.split('.')
            current = self.config
            for section in sections:
                if section not in current:
                    return None
                current = current[section]
            return current
        else:
            return self.config.get(key)
    
    def reset_config(self):
        """Reset configuration to defaults."""
        self.config = self.DEFAULT_CONFIG.copy()
        return self.save_config()

def main():
    parser = argparse.ArgumentParser(description="Notes Digest Configuration Utility")
    parser.add_argument('--config', type=str, default='config.json', help='Path to configuration file')
    parser.add_argument('--setup', action='store_true', help='Run interactive setup')
    parser.add_argument('--print', action='store_true', help='Print current configuration')
    parser.add_argument('--reset', action='store_true', help='Reset configuration to defaults')
    parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'), help='Set a configuration option')
    parser.add_argument('--get', type=str, metavar='KEY', help='Get a configuration option')
    
    args = parser.parse_args()
    
    config_util = ConfigUtility(args.config)
    
    if args.reset:
        if config_util.reset_config():
            print("Configuration reset to defaults")
        else:
            print("Error resetting configuration")
    elif args.setup:
        config_util.interactive_setup()
    elif args.print:
        config_util.print_config()
    elif args.set:
        key, value_str = args.set
        
        # Try to convert string value to appropriate type
        try:
            if value_str.lower() == 'true':
                value = True
            elif value_str.lower() == 'false':
                value = False
            elif value_str.isdigit():
                value = int(value_str)
            elif '.' in value_str and all(p.isdigit() for p in value_str.split('.', 1)):
                value = float(value_str)
            else:
                value = value_str
        except Exception:
            value = value_str
        
        if config_util.set_option(key, value):
            print(f"Set {key} = {value}")
        else:
            print(f"Error setting {key}")
    elif args.get:
        value = config_util.get_option(args.get)
        if value is not None:
            print(f"{args.get} = {value}")
        else:
            print(f"Option {args.get} not found")
    else:
        # Default: print current configuration and offer to run setup
        config_util.print_config()
        print("\nRun with --setup to configure settings")

if __name__ == "__main__":
    main()