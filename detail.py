import sys; sys.argv=["x"]
exec(open("ichimoku_search.py").read().split("grid = itertools")[0])
N=len(full)
def detail(side,ref,thr,ex,stop=None,mh=None):
    tr,op=run(side,ref,thr,ex,stop,mh,0,N)
    rows=[]
    for j,i,r in tr:
        mae=(c[j:i+1].min()/c[j]-1)*100
        rows.append((dates[j].date(),dates[i].date(),round(c[j]),round(c[i]),i-j,round(r,2),round(mae,2)))
    d=pd.DataFrame(rows,columns=["entry","exit","in","out","days","ret%","worst_dip%"])
    print(f"\n### {side} {ref} {thr}% exit={ex} stop={stop}")
    print(d.to_string(index=False))
    eq=np.prod(1+d["ret%"]/100)-1
    print(f"trades {len(d)} wins {(d['ret%']>0).sum()} compounded {eq*100:.1f}%  avg {d['ret%'].mean():.2f}%  avg hold {d.days.mean():.0f}d  max hold {d.days.max()}d  deepest dip {d['worst_dip%'].min():.1f}%")
    if op: print(f"OPEN now: in {dates[op[0]].date()} @ {op[1]:.0f}, last close {c[-1]:.0f} ({(c[-1]/op[1]-1)*100:+.2f}%), deepest {(c[op[0]:].min()/op[1]-1)*100:.1f}%")
detail("long","tenkan",2,3.0)
detail("long","kijun",2,5.0)
