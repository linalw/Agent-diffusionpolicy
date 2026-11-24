import sys, time; sys.path.insert(0,'src')
import numpy as np, torch
from fruit_sorting.policy.runtime import PolicyRunner
for ck in ('checkpoints/p227_panda156/policy_best.pt','checkpoints/p227_panda1e/policy_best.pt'):
    p=PolicyRunner(ck, device='cuda')
    g=torch.randn(1,8,device='cuda'); pr=torch.randn(1,12,device='cuda')
    p._frames=[np.zeros((128,128,5),dtype=np.float32) for _ in range(2)]
    for _ in range(5): p.act(np.zeros(12,dtype=np.float32), np.zeros(8,dtype=np.float32), num_steps=16)
    t=[]
    for _ in range(30):
        t0=time.perf_counter(); p.act(np.zeros(12,dtype=np.float32), np.zeros(8,dtype=np.float32), num_steps=16); t.append((time.perf_counter()-t0)*1e3)
    n=sum(x.numel() for x in p.model.parameters())
    print(f"{ck.split('/')[1]:16s} params {n/1e6:.2f}M   latency p50 {np.median(t):6.1f} ms  p95 {np.percentile(t,95):6.1f} ms")
