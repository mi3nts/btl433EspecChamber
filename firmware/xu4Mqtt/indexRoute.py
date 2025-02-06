import json, requests
rsp = requests.get(
    "http://192.168.20.128/api/v4/",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")