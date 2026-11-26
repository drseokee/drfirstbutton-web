import sys, json
T = "/home/claude/sh/tpl/"
head = open(T + "p1_head.html").read().replace("<title>요추 압박골절 — 3D 환자 설명</title>", "<title>어깨 회전근개 — 3D 환자 설명</title>")
tpl = head + open(T + "p2_body.html").read() + "\n" + open(T + "p3_common.js").read() + open(T + "p4_main.js").read() + open(T + "p5_tail.html").read()
REPO = "/home/user/drfirstbutton-web/"
open(REPO + "pipeline/rotator-cuff/viewer_shoulder_template.html", "w").write(tpl)
data = open("/home/claude/out_shoulder/model.json").read()
open(REPO + "site/diseases/rotator-cuff/3d.html", "w").write(tpl.replace("__DATA__", data))
print("built", len(tpl), len(data))
