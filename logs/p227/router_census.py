import sys; sys.path.insert(0,'src')
import numpy as np, torch
from fruit_sorting.policy.runtime import PolicyRunner
from fruit_sorting.policy.data import EpisodeStore
from fruit_sorting.policy.skills import SKILLS
pol=PolicyRunner('checkpoints/p227_panda156/policy_best.pt', device='cuda')
st=EpisodeStore('datasets/p227_panda_all', obs_horizon=2, action_horizon=16, image_size=128, only_successful=False)
rng=np.random.RandomState(7); sel=np.sort(rng.choice(len(st), 400, replace=False))
w_all=[]; per_skill={}
for i in sel:
    o=st[int(i)]
    img=np.asarray(o["image"],dtype=np.float32)
    pol._frames=[np.transpose(img[k],(1,2,0)) for k in range(img.shape[0])]
    p=np.asarray(o["proprio"],dtype=np.float32)[:12]; g=np.asarray(o["goal"],dtype=np.float32)
    with torch.no_grad():
        with torch.autocast('cuda', dtype=torch.float16, enabled=pol.use_half):
            _ = pol.act(p, g, num_steps=1)
    w=pol.model.last_router_weights[0].float().cpu().numpy()
    w_all.append(w)
    s=SKILLS[int(o["skill"])]
    per_skill.setdefault(s, []).append(w)
W=np.array(w_all)
print("router weights over 400 random windows (skills: %s)" % ", ".join(SKILLS))
print("  p50 :", np.round(np.median(W,0),3).tolist())
print("  p05 :", np.round(np.percentile(W,5,axis=0),3).tolist())
print("  argmax counts:", np.bincount(W.argmax(1), minlength=len(SKILLS)).tolist())
for s,ws in per_skill.items():
    A=np.array(ws)
    print(f"  {s:9s} n={len(ws):3d}  mean weights {np.round(A.mean(0),3).tolist()}  argmax {np.bincount(A.argmax(1), minlength=5).tolist()}")
