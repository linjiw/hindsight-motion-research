"""Offline input-reference jumps at frozen handoff indices; no physics/model inference."""
import argparse
import json
from pathlib import Path

import numpy as np

from hindsight_motion.core import sha256


def main(packet):
    packet = Path(packet).resolve()
    output = packet / "offline-input-diagnostics.json"
    if output.exists():
        raise FileExistsError("Preserve the original offline diagnostic receipt")
    plan = json.loads((packet / "plan.json").read_text())
    rows, parents = [], []
    for clip in plan["registration"]["source_clips"]:
        base = Path(next(c["parent_run"] for c in plan["cases"] if c["source_clip"]==clip)).parent.parent
        refs=[]
        for method in ["continuous","linear29"]:
            path=base / "references" / f"{clip}_{method}/reference.npz"
            parents.append(dict(path=str(path),sha256=sha256(path)))
            with np.load(path) as d:
                refs.append(d["qpos"][:,7:].copy())
                names=d["joint_names"].tolist()
        delta=refs[1]-refs[0]
        velocity_delta=np.diff(delta,axis=0)/.02
        nonwrist=[i for i,name in enumerate(names) if not ("wrist_pitch" in name or "wrist_yaw" in name)]
        for c in plan["cases"]:
            if c["source_clip"]!=clip or c["method"]!="linear29":continue
            k=c["handoff_tick"]
            row=abs(delta[k]);max_i=int(np.argmax(row))
            rows.append(dict(source_clip=clip,state=c["state"],handoff_tick=k,handoff_time_s=k*.02,
                             input_joint_max_rad=float(row.max()),max_joint=names[max_i],
                             nonwrist_input_joint_max_rad=float(row[nonwrist].max()),
                             input_forward_difference_velocity_max_rad_s=float(abs(velocity_delta[k]).max())))
    receipt=dict(schema="hindsight_continuation_offline_input_v1",physics_steps=0,
                 scope="Input-qpos reference differences, not native action effects or executed outcomes",
                 source_sha256=sha256(__file__),rows=rows,parents=parents)
    with output.open("x") as f:json.dump(receipt,f,indent=2);f.write("\n")
    print(json.dumps({"physics_steps":0,"rows":rows},indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet",type=Path)
    main(parser.parse_args().packet)
