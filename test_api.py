import urllib.request, urllib.error, json, sys

data = json.dumps({"message": "分析抖音和快手"}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/tasks/",
    data=data,
    headers={"Content-Type": "application/json"},
)
try:
    resp = urllib.request.urlopen(req, timeout=120)
    print("STATUS:", resp.status)
    result = json.loads(resp.read().decode())
    print("TASK_ID:", result["task_id"])
    print("STATUS:", result["status"])
    print("COMPETITORS:", result["competitors"])
    print("DIMENSIONS:", result["dimensions"])

    import time
    for i in range(30):
        time.sleep(2)
        req2 = urllib.request.Request(
            f"http://localhost:8001/api/tasks/{result['task_id']}",
            headers={},
        )
        resp2 = urllib.request.urlopen(req2, timeout=10)
        task = json.loads(resp2.read().decode())
        print(f"  Poll {i+1}: status={task['status']}, nodes={list(task['node_states'].keys())}")
        if task["status"] in ("completed", "failed"):
            print("FINAL:", json.dumps(task, indent=2, ensure_ascii=False))
            break
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP ERROR {e.code}: {body}", file=sys.stderr)
    try:
        detail = json.loads(body).get("detail", "")
        print(f"Decoded detail: {detail}", file=sys.stderr)
    except:
        pass
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
    import traceback; traceback.print_exc()
    sys.exit(1)