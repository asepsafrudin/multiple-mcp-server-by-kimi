from google.oauth2 import service_account
path = "/home/aseps/MCP/config/credentials/vision-primary.json"
credentials = service_account.Credentials.from_service_account_file(
    path,
    scopes=["https://www.googleapis.com/auth/cloud-vision"],
)
print("Token before refresh:", credentials.token)
import google.auth.transport.requests
request = google.auth.transport.requests.Request()
credentials.refresh(request)
print("Token after refresh:", credentials.token is not None)
