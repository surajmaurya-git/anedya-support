import requests
from authlib.integrations.flask_client import OAuth
from flask import Flask, jsonify, redirect, render_template, session, url_for

app = Flask(__name__)
app.secret_key = "55KlBg20aDrDdj37QWGQi7MCEl6i4PHqmjRnJopcZTJDa5vXQcfdDMDjuHvqOZRx"
oauth = OAuth(app)

oauth.register(
    name="my_platform",
    client_id="NdoorlVV1Xyb7QUzPv46b5Xi6oUybGC1",
    server_metadata_url="https://auth.sandbox.anedyacloud.com/.well-known/openid-configuration",
    client_kwargs={"scope": "project openid"},
)


@app.route("/")
def home():
    user = session.get("user")
    token = session.get("token")
    return render_template("index.html", user=user, token=token)


@app.route("/login")
def login():
    redirect_uri = url_for("auth_callback", _external=True)
    return oauth.my_platform.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    # Exchange the authorization code for an access token
    token = oauth.my_platform.authorize_access_token()

    # Save token in session for future API calls
    session["token"] = token

    # Fetch user profile
    user_info = oauth.my_platform.userinfo()
    session["user"] = dict(user_info)

    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/api/nodes")
def get_nodes():
    token = session.get("token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401

    access_token = token["access_token"]

    resp = requests.post(
        "https://api.sandbox.anedyacloud.com/v1/node/list",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-anedya-project": "bfd253ae-20d5-4d8c-8fa9-4bd520b2b273",
        },
        json={"order": "asc"},
    )

    print("Response Status:", resp.status_code)
    print("Response Body:  ", resp.text)

    if not resp.text:
        return jsonify(
            {"error": "Empty response from server", "status_code": resp.status_code}
        ), resp.status_code

    return jsonify(resp.json())


if __name__ == "__main__":
    app.run(debug=True)
