import json, requests
import time

import json, requests
rsp = requests.get(
    "http://192.168.20.113/api/v4/chambers/1/operations",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")

# rsp = requests.get(
#     "http://192.168.20.128/api/v4/chambers/",
#     headers={
#         "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
#     },
# )
# data = json.dumps(rsp.json(), indent=4)
# print(f"StatusCode={rsp.status_code}\n\n{data}")


# rsp = requests.get(
#     "http://192.168.20.128/api/v4/chambers/1",
#     headers={
#         "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
#     },
# )
# data = json.dumps(rsp.json(), indent=4)
# print(f"StatusCode={rsp.status_code}\n\n{data}")


# rsp = requests.get(
#     "http://192.168.20.128/api/v4/chambers/1",
#     headers={
#         "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
#     },
# )
# data = json.dumps(rsp.json(), indent=4)
# print(f"StatusCode={rsp.status_code}\n\n{data}")


# rsp = requests.get(
#     "http://192.168.20.128/api/v4/chambers/1/constants",
#     headers={
#         "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
#     },
# )
# data = json.dumps(rsp.json(), indent=4)
# print(f"StatusCode={rsp.status_code}\n\n{data}")


# import json, requests
# body = {
#     "temp": {
#         "group": "loop",
#         "set_value": 15,
#         "range": [
#             -20,
#             180
#         ]
#     },
#     "humi": {
#         "group": "loop",
#         "enable": true,
#         "set_value": 61,
#         "range": [
#             10,
#             95
#         ]
#     },
#     "time_signal_1": {
#         "group": "output",
#         "value": true
#     },
#     "dap": {
#         "group": "output",
#         "value": false
#     }
# }
# rsp = requests.post(
#     "http://192.168.20.128/api/v4/chambers/1/constants",
#     headers={
#         "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo",
#         "Content-Type": "application/json;charset=utf-8"
#     },
#     data=body
# )
# data = json.dumps(rsp.json(), indent=4)
# print(f"StatusCode={rsp.status_code}\n\n{data}")

import json, requests
rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/conditions",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")


import json, requests
rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/conditions/status",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")


rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/conditions/temp",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")


rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/conditions/humi",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")


rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/conditions/time_signal_1",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")


rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/conditions/dap",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")


rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/operations",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")


rsp = requests.get(
    "http://192.168.20.128/api/v4/chambers/1/operations/start_constant",
    headers={
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo"
    },
)
data = json.dumps(rsp.json(), indent=4)
print(f"StatusCode={rsp.status_code}\n\n{data}")




# Set Constant 
import requests

# API details
url = "http://192.168.20.128/api/v4/chambers/1/constants/constant_1"
headers = {
    "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo",
    "Content-Type": "application/json"
}

# JSON payload
data = {
    "temp": {"group": "loop", "set_value": 15, "range": [-20, 180]},
    "humi": {"group": "loop", "enable": True, "set_value": 61, "range": [10, 95]},
    "time_signal_1": {"group": "output", "value": True},
    "dap": {"group": "output", "value": False}
}

try:
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    print("Response:", response.json())
except requests.exceptions.HTTPError as err:
    print("HTTP Error:", err)
except Exception as e:
    print("Error:", e)


time.sleep(1)


url = "http://192.168.20.128/api/v4/chambers/1/operations/start_constant"
headers = {
    "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo",
    "Content-Type": "application/json;charset=utf-8"
}
data = {"group": "constant"}

try:
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    print("Success:", response.json())
except requests.exceptions.RequestException as e:
    print("Error:", e)



time.sleep(60)



url = "http://192.168.20.128/api/v4/chambers/1/operations/stop_chamber"
headers = {
    "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo",
    "Content-Type": "application/json;charset=utf-8"
}
data = {"group": "standby"}

response = requests.post(url, headers=headers, json=data)

if response.ok:
    print("Success:", response.json())
else:
    print("Error:", response.status_code, response.text)
