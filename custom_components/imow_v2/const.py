DOMAIN = "imow_v2"
MANUFACTURER = "STIHL"
DEFAULT_SCAN_INTERVAL = 10  # minutes

# Azure B2C PKCE constants (pre-verified, accepted by STIHL B2C)
PKCE_CODE_VERIFIER  = "vMkOO8V_7wUJnNMJY9e0QAQZyjhXDmOQvw_vWZgQZlo"
PKCE_CODE_CHALLENGE = "tVL4sat5ICtwTzAYgTRY51yCElsZE3Y3NScIcBRFe5o"
B2C_CLIENT_ID       = "0d947284-c186-454e-96fd-0094f4510b3f"
B2C_REDIRECT_URI    = "imow://www.imow.com/welcome/login"
B2C_POLICY          = "b2c_1a_production_flow_signin"
B2C_POLICY_MIXED    = "B2C_1A_production_Flow_SignIn"
B2C_BASE            = "https://login.stihl.com/stihlidproduction.onmicrosoft.com"
B2C_AUTHORIZE_URL   = f"{B2C_BASE}/{B2C_POLICY}/oauth2/v2.0/authorize"
B2C_TOKEN_URL       = f"{B2C_BASE}/{B2C_POLICY}/oauth2/v2.0/token"
B2C_SCOPE           = "offline_access https://login.stihl.com/scopes/profile openid"

APIM_KEY            = "52659909060946fc88f2d3368c16d9c7"
API_BASE            = "https://apim.stihl.cloud"
API_MOWERS          = f"{API_BASE}/imow/p/mowertwin/api/v1/mowers"
API_DASHBOARD       = f"{API_BASE}/imow/p/mowertwin/api/v1/dashboard-status/{{id}}?force-status-update-mode=force"
API_MOWING_PLAN     = f"{API_BASE}/imow/p/mowertwin/api/v1/mowing-plans/{{id}}"
API_WEATHER         = f"{API_BASE}/imow/p/api/v1/weather/daily/{{id}}"
API_SIGNALR_NEG     = f"{API_BASE}/imow/p/signalr/api/v1/negotiate?negotiateVersion=1"
API_COMMAND         = f"{API_BASE}/imow/p/mowerctrl/api/v1/mower-commands/{{id}}/{{cmd}}"
API_STATISTICS      = f"{API_BASE}/imow/p/mowertwin/api/v1/statistics/{{id}}"

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
