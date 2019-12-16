from . import app_config

MANAGE_SUBSCRIPTION_PAGE = 'managesubscription.html'
SUBSCRIPTION_OPERATIONS_PAGE = 'suboperations.html'
ERROR_PAGE = 'error.html'
SEND_DIMENSION_USAGE_PAGE = 'senddimensionusage.html'
_404_PAGE = '404.html'
_500_PAGE = '500.HTML'

RESOLVE_ENDPOINT = f"{app_config.MARKETPLACEAPI_ENDPOINT}resolve{app_config.MARKETPLACEAPI_API_VERSION}"
MARKETPLACE_TOKEN_ENDPOINT = f"{app_config.AUTHORITY}{app_config.TENANT_ID}/oauth2/token"
GET_SUBSCRIPTIONS_ENDPOINT = app_config.MARKETPLACEAPI_ENDPOINT + app_config.MARKETPLACEAPI_API_VERSION
SEND_DIMENSION_USAGE_ENDPOINT = app_config.MARKETPLACEAPI_USAGE_ENDPOINT + app_config.MARKETPLACEAPI_API_VERSION


def ACTIVATE_SUBSCRIPTION_ENDPOINT(subscription_id):
    return f"{app_config.MARKETPLACEAPI_ENDPOINT}{subscription_id}/activate{app_config.MARKETPLACEAPI_API_VERSION}"


def GET_SUBSCRIPTION_ENDPOINT(subscription_id):
    return f"{app_config.MARKETPLACEAPI_ENDPOINT}{subscription_id}{app_config.MARKETPLACEAPI_API_VERSION}"


def GET_SUBSCRIPTION_PLANS(subscription_id):
    return f"{app_config.MARKETPLACEAPI_ENDPOINT}{subscription_id}/listAvailablePlans{app_config.MARKETPLACEAPI_API_VERSION}"


def UPDATE_SUBSCRIPTION_ENDPOINT(subscription_id):
    return f"{app_config.MARKETPLACEAPI_ENDPOINT}{subscription_id}{app_config.MARKETPLACEAPI_API_VERSION}"


def GET_SUBSCRIPTION_OPERATIONS_ENDPOINT(subscription_id):
    return f"{app_config.MARKETPLACEAPI_ENDPOINT}{subscription_id}/operations{app_config.MARKETPLACEAPI_API_VERSION}"


def GET_UPDATE_SUBSCRIPTION_OPERATION_ENDPOINT(subscription_id, operation_id):
    return f"{app_config.MARKETPLACEAPI_ENDPOINT}{subscription_id}/operations/{operation_id}{app_config.MARKETPLACEAPI_API_VERSION}"
