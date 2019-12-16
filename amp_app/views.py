from flask import (
    Flask, jsonify, redirect, render_template, request, session, url_for, flash)

from flask_session import Session
from . import amprepo, app_config, constant, utils, app
from functools import wraps
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import datetime
import pytz
import logging
import uuid
import msal
import json

app.config.from_object(app_config)
Session(app)
requested_url = ''


# -----------------------------------------------------------
# Implement Gunicorn logging
# https://medium.com/@trstringer/logging-flask-and-gunicorn-the-manageable-way-2e6f0b8beb2f
# -----------------------------------------------------------
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)


# -----------------------------------------------------------
# Login Decorator
# -----------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# -----------------------------------------------------------
# 404 page handler
# -----------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template(constant._404_PAGE), 404


# -----------------------------------------------------------
# 500 page handler
# -----------------------------------------------------------
@app.errorhandler(500)
def internal_error(e):
    return render_template(constant._500_PAGE), 500


# -----------------------------------------------------------
# Login page redirect - makes sure the user is logged in
# -----------------------------------------------------------
@app.route("/")
def login():
    if not session.get("user"):
        session["state"] = str(uuid.uuid4())
        auth_url = utils._build_msal_app().get_authorization_request_url(
                        [],
                        state=session["state"],
                        redirect_uri=url_for("authorized", _external=True, _scheme=app_config.HTTP_SCHEME))
        return redirect(auth_url, code=302)
    else:
        global requested_url
        if requested_url:
            return redirect(requested_url)
        else:
            return redirect(url_for("dashboard"))


# -------------------------------------------------------------------------
# Redirect/callback path, when the login is succesful validated by Azure AD
# -------------------------------------------------------------------------
@app.route(app_config.REDIRECT_PATH)
def authorized():
    if request.args.get('state') == session.get("state"):
        cache = utils._load_cache()
        result = utils._build_msal_app(cache=cache).acquire_token_by_authorization_code(
            request.args['code'],
            scopes=[],  # Misspelled scope would cause an HTTP 400 error here
            redirect_uri=url_for("authorized", _external=True, _scheme=app_config.HTTP_SCHEME))
        if "error" in result:
            return "Login failure: %s, %s" % (
                result["error"], result.get("error_description"))
        session["user"] = result.get("id_token_claims")
        session["isadmin"] = "@microsoft.com" in result.get("id_token_claims")['preferred_username']
        utils._save_cache(cache)
    return redirect(url_for("login"))


# -----------------------------------------------------------
# Subscription Dashboard page - List all subscriptions
# -----------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    subscriptions_root = amprepo.get_subscriptions()
    subscriptions = subscriptions_root['subscriptions']
    return render_template('index.html', user=session["user"], subscriptions=subscriptions, version=msal.__version__)


# -----------------------------------------------------------
# Subscription Edit page - update/unsubscribe
# -----------------------------------------------------------
@app.route("/edit/<subscriptionid>", methods=['GET', 'POST'])
@login_required
def edit(subscriptionid):
    subscription = amprepo.get_subscription(subscriptionid)
    plans = amprepo.get_availableplans(subscriptionid)

    if request.method == 'POST':
        selected_subscription = subscriptionid
 
        if 'activate' in request.form:
            selected_plan = request.form.get('subscription_plan_id')
            selected_quantity = request.form.get('subscription_activate_quantity', '')
            response = amprepo.activate_subscriptionplan(selected_subscription, selected_plan, selected_quantity)
        elif 'update' in request.form:
            update_key = request.form.get('update')
            update_value = request.form.get(request.form.get('update'))
            response = amprepo.update_subscriptionplan(selected_subscription, update_key, update_value)
        else:
            return redirect(url_for(constant.ERROR_PAGE))

        if response.status_code:
            flash(f'{response.status_code}  {response.text}')
        else:
            flash('No response, update not successfully')
    
    return render_template(constant.MANAGE_SUBSCRIPTION_PAGE, user=session["user"], subscription=subscription, available_plans=plans)


# --------------------------------------------------------------------
# Operations page - list all operations from webhook/ISV operations
# --------------------------------------------------------------------
@app.route("/operations/<subscriptionid>")
@login_required
def operations(subscriptionid):
    subname = request.args.get('subscriptionname')
    sub_operations_by_subid = amprepo.get_sub_operations(subscriptionid)
    sub_operations_by_webhook = amprepo.get_sub_operations_webhook(subscriptionid)
    sub_operations_by_isv = amprepo.get_sub_operations_isv(subscriptionid)
    return render_template(constant.SUBSCRIPTION_OPERATIONS_PAGE, user=session["user"], subsciptionname=subname, subscriptionid=subscriptionid, operations=sub_operations_by_subid, webhookops=sub_operations_by_webhook, isvops=sub_operations_by_isv)


# --------------------------------------------------------------------
# Send Dimension Usage page - send dimension usage - metered billing
# --------------------------------------------------------------------
@app.route("/usage/<subscriptionid>", methods=['GET', 'POST'])
@login_required
def usage(subscriptionid):
    get_data = {} 
    get_data['subname'] = request.args.get('subscriptionname')
    get_data['planId'] = request.args.get('planid')
    get_data['offerId'] = request.args.get('offerid')
    filtered_dimensions_by_offer = None
    if app_config.Dimension_Data:
        dimensions = json.loads(app_config.Dimension_Data)
        filtered_dimensions_by_offer = dimensions.get(request.args.get('offerid'))
        app.logger.error(filtered_dimensions_by_offer)
    get_data['filtered_dimensions_by_offer'] = filtered_dimensions_by_offer
    if request.method == 'POST':
        api_data = {}
        api_data['quantity'] = request.form.get('quantity')
        api_data['selected_dimension'] = request.form.get('selecteddimension')
        month = request.form.get('mm')
        year = request.form.get('yy')
        day = request.form.get('dd')
        hour = request.form.get('hh')
        minute = request.form.get('min')
        usage_datetime_str = f'{month}/{day}/{year} {hour}:{minute}'
        usagetime = datetime.strptime(usage_datetime_str, '%m/%d/%Y %H:%M')
        local_timezone = pytz.timezone('US/Pacific')
        usagetime_tz = local_timezone.localize(usagetime, is_dst=None)
        usagetime_tz_utc = usagetime_tz.astimezone(pytz.utc)

        api_data['local_usage_datetime_object'] = usagetime_tz
        api_data['utc_usage_datetime_object'] = usagetime_tz_utc
        api_data['subname'] = get_data.get('subname')
        api_data['planId'] = get_data.get('planId')
        api_data['offerId'] = get_data.get('offerId')
        api_data['subscriptionid'] = subscriptionid

        # send usage to api
        response = amprepo.send_dimension_usage(api_data)

        if response.status_code:
            flash(f'{response.status_code}  {response.text}')
        else:
            flash('No response, update not successfully')

        api_data['response'] = response.status_code
        api_data['response_message'] = response.text

        # save it in the table storage
        now = datetime.now()
        api_data['RowKey'] = now.strftime('%Y%m%d%H%M%S')
        api_data['senttime'] = now.strftime('%Y-%m-%d %H:%M:%S')
        api_data['PartitionKey'] = subscriptionid
        amprepo.save_sent_dimension_usage(api_data)

    # get the past sent usage pass it to display
    get_data['existingUsage'] = amprepo.get_sent_dimension_usage_by_suscription(subscriptionid)

    return render_template(constant.SEND_DIMENSION_USAGE_PAGE, user=session["user"], data=get_data)


# --------------------------------------------------------------------
# Operation Edit page - update success/failure
# --------------------------------------------------------------------
@app.route("/updateoperation/<operationid>", methods=['GET', 'POST'])
@login_required
def updateoperation(operationid):
    subid = request.args.get('subid')
    planid = request.args.get('planid')
    quantity = request.args.get('quantity')
    subsciptionname = request.args.get('subsciptionname')

    if request.method == 'POST':
        status = ''
        if 'success' in request.form:
            status = 'Success'
        elif 'failure' in request.form:
            status = 'Failure'

        response = amprepo.update_sub_operation(subid, operationid, planid, quantity, status)

        if response.status_code:
            flash(f'{response.status_code}  {response.text}')
        else:
            flash('No response, update not successfully')

    return render_template("suboperationmanage.html", user=session["user"], operationid=operationid,subid=subid, planid=planid, quantity=quantity, subsciptionname=subsciptionname)


# --------------------------------------------------------------------
# Webhook Ednpoint to receive notifications
# --------------------------------------------------------------------
@app.route("/webhook", methods=['POST'])
def webhook():

    try:
        utils._validate_jwt_token(request.headers.get('Authorization'))
        request_payload = request.get_json(force=True)
        request_payload["PartitionKey"] = request_payload.get('subscriptionId')
        request_payload["RowKey"] = request_payload.get('id')
        utils._store_in_azure_table(app_config.WEBHOOK_OPS_STORAGE_TABLE_NAME, request_payload)
        
        subject = 'Webhook notification for Subscription '+ request_payload.get('subscriptionId')
        email_body = utils._get_webhook_email_body(request_payload)
        message = Mail(
            from_email=app_config.SENDGRID_FROM_EMAIL,
            to_emails=app_config.SENDGRID_TO_EMAIL,
            subject=subject,
            html_content=email_body)
        try:
            sendgrid_client = SendGridAPIClient(app_config.SENDGRID_APIKEY)
            response = sendgrid_client.send(message)
            flash(f'{response.status_code} Message sent successfully')
        except Exception as e:
            flash(e.message, 'error')

        return jsonify(), 201
    except Exception as e:
        app.logger.error(e)
        return jsonify("An exception occurred"), 500


@app.route("/privacy")
def privacy():
    return 'This is a sample privacy policy'


@app.route("/logout")
def logout():
    session.clear()  # Wipe out user and its token cache from session
    return redirect(  # Also logout from your tenant's web session
        app_config.AUTHORITY + "/" + app_config.TENANT_ID + "/oauth2/v2.0/logout" +
        # app_config.AUTHORITY + "/common/oauth2/v2.0/logout" +
        "?post_logout_redirect_uri=" + url_for("login", _external=True, _scheme=app_config.HTTP_SCHEME))


@app.before_request
def before_request_func():
    global requested_url
    auth_endpoint_list = ['authorized', 'login', 'webhook']
    if not session.get("user") and request.endpoint not in auth_endpoint_list:
        requested_url = request.url

    if session.get("user") and request.endpoint not in auth_endpoint_list:
        requested_url = None
