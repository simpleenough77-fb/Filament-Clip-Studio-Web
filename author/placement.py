"""Rectangle packing with printer keep-outs and center-first ordering."""
import math
from print_geometry import footprint

GAP = 3.0
MARGIN = 5.0

def intersects(a,b):
    return a[0]<b[2]-1e-6 and a[2]>b[0]+1e-6 and a[1]<b[3]-1e-6 and a[3]>b[1]+1e-6

def subtract(free, used):
    result=[]
    for a in free:
        if not intersects(a,used):result.append(a);continue
        x,y,X,Y=a;u,v,U,V=used
        if x<u:result.append([x,y,u,Y])
        if X>U:result.append([U,y,X,Y])
        if y<v:result.append([x,y,X,v])
        if Y>V:result.append([x,V,X,Y])
    return [a for i,a in enumerate(result) if a[2]-a[0]>1e-6 and a[3]-a[1]>1e-6 and not any(i!=j and b[0]<=a[0] and b[1]<=a[1] and b[2]>=a[2] and b[3]>=a[3] and (a!=b or j<i) for j,b in enumerate(result))]

def space(printer, two_color):
    r=printer['usable'] if two_color else printer['single']
    area=[r[0]+MARGIN,r[1]+MARGIN,r[2]-MARGIN,r[3]-MARGIN]
    blocks=[]
    if printer['exclusions']:
        pts=[list(map(float,s.lower().split('x'))) for s in printer['exclusions']]
        blocks.append([min(p[0] for p in pts)-GAP,min(p[1] for p in pts)-GAP,max(p[0] for p in pts)+GAP,max(p[1] for p in pts)+GAP])
    tower=None
    if two_color:
        # Leave a 76 x 76 mm rear corner for the 60 mm prime tower and brim.
        tower=[area[2]-76,area[3]-76,area[2],area[3]];blocks.append(tower)
    return area,blocks,tower

def pack(items,printer,two_color=True):
    area,blocks,tower=space(printer,two_color)
    initial=[area[:]]
    for b in blocks:initial=subtract(initial,b)
    trials=[]
    for strategy in ('short','area','bottom'):
      for rotation in (False,True):
        remaining=sorted(items,key=lambda a:(-a['w']*a['h'],a['variant']))
        plates=[]
        while remaining:
            free=[x[:] for x in initial];placed=[]
            while remaining:
                options=[]
                for i,item in enumerate(remaining):
                  for turn in ([False,True] if rotation else [False]):
                    w,h=(item['h'],item['w']) if turn else (item['w'],item['h'])
                    for a in free:
                        W,H=a[2]-a[0],a[3]-a[1]
                        if w+GAP>W+1e-6 or h+GAP>H+1e-6:continue
                        score=(min(W-w-GAP,H-h-GAP),max(W-w-GAP,H-h-GAP)) if strategy=='short' else (W*H-(w+GAP)*(h+GAP),min(W-w,H-h)) if strategy=='area' else (a[1]+h,a[0])
                        options.append((score,i,turn,a[0],a[1],w,h))
                if not options:break
                _,i,turn,x,y,w,h=min(options)
                item=remaining.pop(i);placed.append(dict(item,x=x+GAP/2,y=y+GAP/2,w=w,h=h,rotated=turn))
                free=subtract(free,[x,y,x+w+GAP,y+h+GAP])
            if not placed:raise ValueError('This clip does not fit the selected printer with the required clearances.')
            # Move the complete arrangement toward the bed center without moving
            # clips into a keep-out; retain relative spacing and packing density.
            cx=(area[0]+area[2])/2;cy=(area[1]+area[3])/2
            x0=min(i['x'] for i in placed);x1=max(i['x']+i['w'] for i in placed)
            y0=min(i['y'] for i in placed);y1=max(i['y']+i['h'] for i in placed)
            dx=cx-(x0+x1)/2;dy=cy-(y0+y1)/2
            choices=[]
            for fx,fy in [(1,1),(1,0),(0,1)]:
              for f in range(100,-1,-1):
                sx,sy=dx*fx*f/100,dy*fy*f/100
                if all(not any(intersects([i['x']+sx-GAP/2,i['y']+sy-GAP/2,i['x']+i['w']+sx+GAP/2,i['y']+i['h']+sy+GAP/2],b) for b in blocks) for i in placed):
                    choices.append(((cx-(x0+x1)/2-sx)**2+(cy-(y0+y1)/2-sy)**2,sx,sy));break
            _,sx,sy=min(choices)
            for i in placed:i['x']+=sx;i['y']+=sy
            placed.sort(key=lambda i:(i['x']+i['w']/2-cx)**2+(i['y']+i['h']/2-cy)**2)
            plates.append(dict(items=placed,tower=tower,area=area))
        score=(len(plates),sum((max(i['x']+i['w'] for i in p['items'])-min(i['x'] for i in p['items']))*(max(i['y']+i['h'] for i in p['items'])-min(i['y'] for i in p['items'])) for p in plates))
        trials.append((score,plates))
    return min(trials,key=lambda x:x[0])[1]

def plan(checks,settings,printer):
    groups={}
    rainbow=settings['body_mode']=='filament' or (settings['text_mode']=='filament' and settings['style']!='cut')
    for i,r in enumerate(checks):
        key=r['product'] if rainbow else 'shared'
        groups.setdefault(key,[]).extend(dict(variant=i,w=footprint(r['spool_profile'],settings.get('holder_sleeve')=='yes')[0],h=footprint(r['spool_profile'],settings.get('holder_sleeve')=='yes')[1]) for _ in range(r['quantity']))
    plates=[]
    for key,items in groups.items():
        two_color=settings['style']!='cut' and not(settings['body_mode']==settings['text_mode']=='filament')
        for p in pack(items,printer,two_color):
            p['name']=' / '.join(checks[items[0]['variant']]['lines']) if rainbow else 'Mixed labels'
            plates.append(p)
    cols=math.ceil(math.sqrt(len(plates)))
    for n,p in enumerate(plates):
        p['number']=n+1;p['origin']=[n%cols*printer['bed'][0]*1.2,-(n//cols)*printer['bed'][1]*1.2]
    return plates
