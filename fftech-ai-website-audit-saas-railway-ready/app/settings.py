import os
import json
from google.oauth2 import service_account

class Settings:
    # Existing settings...
    PSI_API_KEY = os.environ.get("PSI_API_KEY")
    
    @property
    def gcp_credentials(self):
        """
        Parses the GOOGLE_APPLICATION_CREDENTIALS_JSON variable.
        This handles the complex private key string from Railway.
        """
        creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not creds_json:
            return None
            
        try:
            creds_dict = json.loads(creds_json)
            # Fix newline characters that often break in environment variables
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            return service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            print(f"Error parsing Google Credentials: {e}")
            return None

settings = Settings()
