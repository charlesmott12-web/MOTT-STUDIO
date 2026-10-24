"""Mott Studio 2.0 beta: multitrack DAW. MIT license."""
import json, os, time, uuid, queue, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import numpy as np
import sounddevice as sd
import soundfile as sf

RATE=44100; BLOCK=512
BG='#15191e'; PANEL='#242b33'; FG='#e8edf1'; GOLD='#d4a75c'; BLUE='#5ca8c8'
class Studio:
 def __init__(self,root):
  self.root=root;root.title('Mott Studio 2.0 | Vintage Recording Room');root.geometry('1260x790');root.configure(bg=BG)
  self.project=None;self.tracks=[];self.clips=[];self.undo=[];self.selected=None;self.mode=tk.StringVar(value='Normal');self.device=tk.StringVar();self.output=tk.StringVar();self.devices=[];self.outputs=[]
  self.position=0.;self.zoom=85.;self.rowheight=88;self.running=False;self.stream=None;self.recorded=[];self.capture_start=0;self.playhead=0;self.meters={};self.events=queue.Queue();self.cache={};self.loop_start=tk.DoubleVar(value=0);self.loop_end=tk.DoubleVar(value=8);self.countin=tk.BooleanVar(value=False);self.metronome=tk.BooleanVar(value=False)
  self.build();self.scan();root.after(80,self.tick);root.protocol('WM_DELETE_WINDOW',self.close)
 def button(self,parent,label,command):return tk.Button(parent,text=label,command=command,bg='#333d47',fg=FG,activebackground='#51606d',activeforeground='white',relief='flat',padx=10,pady=6,font=('Segoe UI',10))
 def build(self):
  menu=tk.Menu(self.root);f=tk.Menu(menu,tearoff=False)
  for label,fn in [('New project',self.new),('Open project',self.open),('Save',self.save),('Import WAV',self.import_wav),('Export stereo WAV',self.export),('Exit',self.close)]:f.add_command(label=label,command=fn)
  menu.add_cascade(label='File',menu=f);e=tk.Menu(menu,tearoff=False);e.add_command(label='Undo',command=self.undo_edit);menu.add_cascade(label='Edit',menu=e);self.root.config(menu=menu)
  top=tk.Frame(self.root,bg=BG);top.pack(fill='x',padx=14,pady=8)
  tk.Label(top,text='MOTT  STUDIO',bg=BG,fg=GOLD,font=('Segoe UI',21,'bold')).pack(side='left');tk.Label(top,text='  2.0 BETA   •   VINTAGE RECORDING ROOM',bg=BG,fg='#8f9eac',font=('Segoe UI',10)).pack(side='left')
  self.status=tk.StringVar(value='Create or open a project to begin.');tk.Label(self.root,textvariable=self.status,bg=BG,fg='#b9c5ce',anchor='w').pack(fill='x',padx=16)
  controls=tk.Frame(self.root,bg=PANEL);controls.pack(fill='x',padx=12,pady=7)
  for label,fn in [('● RECORD',self.record),('▶ PLAY',self.play),('■ STOP',self.stop),('+ TRACK',self.add_track),('IMPORT',self.import_wav),('EXPORT',self.export)]:self.button(controls,label,fn).pack(side='left',padx=3,pady=5)
  ttk.Combobox(controls,textvariable=self.mode,values=['Normal','Time selection','Punch','Loop takes'],width=17,state='readonly').pack(side='left',padx=7)
  tk.Checkbutton(controls,text='Click',variable=self.metronome,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left')
  tk.Checkbutton(controls,text='Count-in',variable=self.countin,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left')
  devices=tk.Frame(self.root,bg=BG);devices.pack(fill='x',padx=12)
  tk.Label(devices,text='Input:',bg=BG,fg=FG).pack(side='left');self.indev=ttk.Combobox(devices,textvariable=self.device,width=36,state='readonly');self.indev.pack(side='left',padx=5)
  tk.Label(devices,text='Output:',bg=BG,fg=FG).pack(side='left');self.outdev=ttk.Combobox(devices,textvariable=self.output,width=36,state='readonly');self.outdev.pack(side='left',padx=5);self.button(devices,'Refresh',self.scan).pack(side='left')
  bar=tk.Frame(self.root,bg=BG);bar.pack(fill='x',padx=14,pady=5)
  for label,var in [('Selection start (s)',self.loop_start),('End (s)',self.loop_end)]:tk.Label(bar,text=label,bg=BG,fg=FG).pack(side='left');tk.Entry(bar,textvariable=var,width=7).pack(side='left',padx=6)
  self.clock=tk.StringVar(value='00:00.00');tk.Label(bar,textvariable=self.clock,bg=BG,fg=GOLD,font=('Consolas',16)).pack(side='right')
  center=tk.Frame(self.root,bg=BG);center.pack(fill='both',expand=True,padx=12)
  self.canvas=tk.Canvas(center,bg='#1a2026',highlightthickness=0,cursor='crosshair');self.canvas.pack(fill='both',expand=True)
  self.canvas.bind('<Button-1>',self.click);self.canvas.bind('<Button-3>',self.context);self.canvas.bind('<Control-MouseWheel>',self.zoom_wheel);self.canvas.bind('<Shift-MouseWheel>',self.height_wheel);self.canvas.bind('<MouseWheel>',self.scroll_wheel);self.canvas.bind('<Configure>',lambda e:self.draw())
  self.menu=tk.Menu(self.root,tearoff=0)
  for label,fn in [('Split at playhead',self.split),('Trim to selection',self.trim),('Move clip',self.move),('Copy clip',self.copy),('Clip gain',self.clip_gain),('Mute/unmute clip',self.clip_mute),('Delete clip',self.delete)]:self.menu.add_command(label=label,command=fn)
  mixhead=tk.Frame(self.root,bg=BG);mixhead.pack(fill='x',padx=12);tk.Label(mixhead,text='ANALOG MIXER',bg=BG,fg=GOLD,font=('Segoe UI',10,'bold')).pack(side='left');self.showmix=tk.BooleanVar(value=True);tk.Checkbutton(mixhead,text='Show mixer',variable=self.showmix,command=self.draw_mixer,bg=BG,fg=FG,selectcolor=PANEL).pack(side='right')
  self.mixer=tk.Frame(self.root,bg=PANEL,height=185);self.mixer.pack(fill='x',padx=12,pady=(0,10));self.draw()
 def scan(self):
  try:
   all_d=sd.query_devices();self.devices=[(f'{i}: {d["name"]}',i,int(d['max_input_channels'])) for i,d in enumerate(all_d) if d['max_input_channels']>0];self.outputs=[(f'{i}: {d["name"]}',i,int(d['max_output_channels'])) for i,d in enumerate(all_d) if d['max_output_channels']>0]
   self.indev['values']=[x[0] for x in self.devices];self.outdev['values']=[x[0] for x in self.outputs]
   if self.devices:self.device.set(next((x[0] for x in self.devices if 'irig' in x[0].lower()),self.devices[0][0]))
   if self.outputs:self.output.set(next((x[0] for x in self.outputs if 'irig' in x[0].lower()),self.outputs[0][0]))
  except Exception as exc:self.status.set(str(exc))
 def chosen(self,items,value):return next((x for x in items if x[0]==value),None)
 def new(self):
  folder=filedialog.askdirectory(title='Choose parent folder');name=simpledialog.askstring('Project','Song name:') if folder else None
  if not name:return
  self.project=Path(folder)/''.join(c if c.isalnum() or c in ' -_' else '_' for c in name);self.project.mkdir(parents=True,exist_ok=True);(self.project/'audio').mkdir(exist_ok=True);self.tracks=[];self.clips=[];self.position=0;self.add_track('Track 1');self.save()
 def open(self):
  folder=filedialog.askdirectory(title='Open Mott Studio project');
  if not folder:return
  try:
   self.project=Path(folder);obj=json.loads((self.project/'project.json').read_text());self.tracks=obj.get('tracks',[]);self.clips=obj.get('clips',[])
   if not self.tracks:
    old=self.clips;self.clips=[]
    for i,c in enumerate(old):self.add_track(c.get('name',f'Track {i+1}'));c['track']=self.tracks[-1]['id'];self.clips.append(c)
   self.cache.clear();self.draw();self.draw_mixer();self.status.set(f'Opened {folder}')
  except Exception as exc:messagebox.showerror('Open failed',str(exc))
 def save(self):
  if not self.project:return
  data={'format':'mott-studio-2.0','sample_rate':RATE,'tracks':self.tracks,'clips':self.clips};tmp=self.project/'project.tmp';tmp.write_text(json.dumps(data,indent=2));os.replace(tmp,self.project/'project.json');self.status.set('Project saved: '+str(self.project))
 def add_track(self,name=None):
  if not self.project:
   create=messagebox.askyesno('Project required', 'Tracks need a project to save into.\n\nCreate a new project now?\n\nChoose No to cancel and open an existing project from File > Open project.')
   if create:
    self.new()  # New project creates Track 1 automatically.
   return
  if not isinstance(name,str):name=f'Track {len(self.tracks)+1}'
  self.snapshot()
  self.tracks.append({'id':uuid.uuid4().hex,'name':name,'input':min(len(self.tracks)+1,2),'arm':True,'mute':False,'solo':False,'gain':1.,'pan':0.});self.draw();self.draw_mixer();self.save()
 def snapshot(self):self.undo.append(json.loads(json.dumps((self.tracks,self.clips))));self.undo=self.undo[-30:]
 def undo_edit(self):
  if self.undo:self.tracks,self.clips=self.undo.pop();self.draw();self.draw_mixer();self.save()
 def audio(self,filename):
  if filename not in self.cache:
   a,r=sf.read(self.project/'audio'/filename,always_2d=True,dtype='float32')
   if r!=RATE:raise ValueError(f'{filename}: sample rate must be 44100 Hz')
   self.cache[filename]=a
  return self.cache[filename]
 def mix_block(self,start,n):
  out=np.zeros((n,2),dtype=np.float32);solos=any(t['solo'] for t in self.tracks)
  for t in self.tracks:
   if t['mute'] or (solos and not t['solo']):continue
   for c in self.clips:
    if c.get('track')!=t['id'] or c.get('mute'):continue
    cs=round(c['start']*RATE);ce=cs+round(c['duration']*RATE);a=max(start,cs);b=min(start+n,ce)
    if b<=a:continue
    source=round(c.get('offset',0)*RATE)+(a-cs);wave=self.audio(c['file']);ch=min(c.get('channel',0),wave.shape[1]-1);segment=wave[source:source+(b-a),ch]
    if not len(segment):continue
    gain=c.get('gain',1)*t['gain'];pan=t['pan'];out[a-start:a-start+len(segment),0]+=segment*gain*min(1,1-pan);out[a-start:a-start+len(segment),1]+=segment*gain*min(1,1+pan)
  return out
 def total(self):return max([c['start']+c['duration'] for c in self.clips]+[0])
 def play(self):self.start(False)
 def record(self):self.start(True)
 def start(self,record):
  if self.running:return
  if not self.project:messagebox.showinfo('Project','Create a project first');return
  inp=self.chosen(self.devices,self.device.get());out=self.chosen(self.outputs,self.output.get());armed=[t for t in self.tracks if t['arm']] if record else []
  if record and (not inp or not armed):messagebox.showerror('Input','Select input and arm at least one track');return
  if not out:messagebox.showerror('Output','Select an output device');return
  if record and inp[1]!=out[1]:
   messagebox.showwarning('Interface routing','For synchronized overdubbing, select the same full-duplex interface for input and output.');return
  self.recorded=[];self.capture_start=int(self.position*RATE);self.playhead=self.capture_start;self.is_record=record;self.armed=armed;self.in_channels=min(inp[2],max([t['input'] for t in armed]+[1]));self.running=True
  try:
   def callback(indata,outdata,frames,timing,status):
    if status:self.events.put(str(status))
    try:
     start=self.playhead;mix=self.mix_block(start,frames);outdata[:]=np.clip(mix,-1,1)
     if self.is_record:self.recorded.append(indata.copy())
     self.playhead+=frames
     if not self.is_record and self.playhead>=int(self.total()*RATE):raise sd.CallbackStop
     if self.is_record and self.mode.get() in ('Punch','Time selection') and self.playhead>=int(self.loop_end.get()*RATE):raise sd.CallbackStop
     if self.is_record and self.mode.get()=='Loop takes' and self.playhead>=int(self.loop_end.get()*RATE):raise sd.CallbackStop
    except sd.CallbackStop:raise
    except Exception as exc:self.events.put('Audio callback error: '+str(exc));outdata.fill(0);raise sd.CallbackStop
   self.stream=sd.Stream(device=(inp[1] if inp else out[1],out[1]),samplerate=RATE,blocksize=BLOCK,channels=(self.in_channels if record else 1, min(2,out[2])),callback=callback,finished_callback=lambda:self.events.put('finished'))
   self.stream.start();self.status.set('RECORDING' if record else 'PLAYING')
  except Exception as exc:self.running=False;self.stream=None;messagebox.showerror('Audio start failed',str(exc))
 def stop(self):
  if not self.running:return
  self.running=False
  if self.stream:
   try:self.stream.stop();self.stream.close()
   except Exception:pass
   self.stream=None
  if self.is_record and self.recorded:
   try:
    a=np.concatenate(self.recorded);filename='take_'+uuid.uuid4().hex[:12]+'.wav';sf.write(self.project/'audio'/filename,a,RATE,subtype='PCM_24');self.snapshot()
    for t in self.armed:
     ch=t['input']-1
     if ch>=a.shape[1]:continue
     start=self.capture_start/RATE;duration=len(a)/RATE
     if self.mode.get() in ('Punch','Time selection'):
      lo=self.loop_start.get();hi=self.loop_end.get();skip=max(0,lo-start);start=max(start,lo);duration=max(0,min(start+duration,hi)-start);offset=skip
     else:offset=0
     if duration>0:self.clips.append({'track':t['id'],'file':filename,'channel':ch,'start':start,'offset':offset,'duration':duration,'gain':1.,'mute':False,'take':self.mode.get()})
    self.save();self.status.set(f'Recorded {len(a)/RATE:.1f}s on {len(self.armed)} armed track(s).')
   except Exception as exc:messagebox.showerror('Save recording failed',str(exc))
  self.draw()
 def import_wav(self):
  if not self.project:return
  fn=filedialog.askopenfilename(filetypes=[('WAV audio','*.wav')]);
  if not fn:return
  try:
   a,r=sf.read(fn,always_2d=True,dtype='float32')
   if r!=RATE:messagebox.showerror('Sample rate','Import currently requires 44,100 Hz WAV.');return
   import shutil
   name='import_'+uuid.uuid4().hex[:8]+'.wav';shutil.copy2(fn,self.project/'audio'/name);self.add_track(Path(fn).stem);self.snapshot();self.clips.append({'track':self.tracks[-1]['id'],'file':name,'channel':0,'start':self.position,'offset':0,'duration':len(a)/RATE,'gain':1.,'mute':False});self.save();self.draw()
  except Exception as exc:messagebox.showerror('Import failed',str(exc))
 def export(self):
  if not self.project or not self.clips:return
  fn=filedialog.asksaveasfilename(defaultextension='.wav',filetypes=[('WAV','*.wav')]);
  if not fn:return
  try:
   with sf.SoundFile(fn,'w',samplerate=RATE,channels=2,subtype='PCM_24') as f:
    for start in range(0,int(self.total()*RATE),RATE*5):f.write(np.clip(self.mix_block(start,min(RATE*5,int(self.total()*RATE)-start)),-1,1))
   self.status.set('Exported '+fn)
  except Exception as exc:messagebox.showerror('Export failed',str(exc))
 def draw(self):
  if not hasattr(self,'canvas'):return
  c=self.canvas;c.delete('all');w=max(c.winfo_width(),100);left=210;end=(w-left)/self.zoom
  for sec in np.arange(0,end+1,max(1,round(90/self.zoom))):
   x=left+sec*self.zoom;c.create_line(x,0,x,max(60,len(self.tracks)*self.rowheight+28),fill='#303941');c.create_text(x+4,12,text=f'{sec:.0f}s',fill='#aeb8c0',anchor='w')
  for i,t in enumerate(self.tracks):
   y=28+i*self.rowheight;c.create_rectangle(0,y,left,y+self.rowheight-2,fill=PANEL,outline='#404a54');c.create_text(12,y+20,text=t['name'],fill=FG,anchor='w',font=('Segoe UI',11,'bold'))
   for j,(label,key) in enumerate([('R','arm'),('M','mute'),('S','solo')]):
    x=12+j*45;c.create_rectangle(x,y+40,x+35,y+65,fill=GOLD if t[key] else '#46515d',outline='');c.create_text(x+17,y+52,text=label,fill='#0c1115' if t[key] else FG,font=('Segoe UI',10,'bold'))
   c.create_rectangle(left,y,w,y+self.rowheight-2,fill='#1d252d',outline='#37414a')
   for idx,clip in enumerate(self.clips):
    if clip.get('track')!=t['id']:continue
    x1=left+clip['start']*self.zoom;x2=x1+clip['duration']*self.zoom
    if x2<left or x1>w:continue
    c.create_rectangle(x1,y+8,x2,y+self.rowheight-10,fill='#3c7786' if idx!=self.selected else '#9b7748',outline='#93c3c7',width=1)
    c.create_text(x1+5,y+15,text=clip['file'],anchor='w',fill='white',font=('Segoe UI',8))
    try:
     wave=self.audio(clip['file']);ch=min(clip.get('channel',0),wave.shape[1]-1);offset=int(clip.get('offset',0)*RATE);count=int(clip['duration']*RATE);s=wave[offset:offset+count,ch];bins=max(1,int(min(x2-x1,1000)))
     if len(s):
      for k in range(bins):
       seg=s[k*len(s)//bins:(k+1)*len(s)//bins];amp=float(np.max(np.abs(seg))) if len(seg) else 0;cx=x1+k*(x2-x1)/bins;mid=y+self.rowheight/2;c.create_line(cx,mid-amp*28,cx,mid+amp*28,fill='#c7e7e2')
    except Exception:pass
  px=left+self.position*self.zoom;c.create_line(px,0,px,max(100,len(self.tracks)*self.rowheight+28),fill='#f0b45d',width=2)
  c.configure(scrollregion=(0,0,w,max(300,28+len(self.tracks)*self.rowheight)))
 def click(self,e):
  row=int((e.y-28)//self.rowheight)
  if not 0<=row<len(self.tracks):return
  t=self.tracks[row];y=e.y-(28+row*self.rowheight)
  if e.x<210:
   if 40<=y<=65:
    idx=int((e.x-12)//45)
    if 0<=idx<3:self.snapshot();key=['arm','mute','solo'][idx];t[key]=not t[key];self.save();self.draw();self.draw_mixer()
  else:
   self.position=max(0,(e.x-210)/self.zoom);self.selected=next((i for i,c in enumerate(self.clips) if c['track']==t['id'] and c['start']<=self.position<=c['start']+c['duration']),None);self.draw()
 def context(self,e):self.click(e);self.menu.tk_popup(e.x_root,e.y_root)
 def zoom_wheel(self,e):self.zoom=max(12,min(600,self.zoom*(1.15 if e.delta>0 else 1/1.15)));self.draw()
 def height_wheel(self,e):self.rowheight=max(58,min(220,self.rowheight+(10 if e.delta>0 else -10)));self.draw()
 def scroll_wheel(self,e):self.canvas.yview_scroll(-1 if e.delta>0 else 1,'units')
 def selected_clip(self):return self.clips[self.selected] if self.selected is not None and self.selected<len(self.clips) else None
 def edit(self,fn):
  c=self.selected_clip()
  if not c:return
  self.snapshot();fn(c);self.save();self.draw()
 def split(self):
  def f(c):
   p=self.position
   if c['start']<p<c['start']+c['duration']:
    right=dict(c,start=p,offset=c.get('offset',0)+p-c['start'],duration=c['start']+c['duration']-p);c['duration']=p-c['start'];self.clips.append(right)
  self.edit(f)
 def trim(self):
  def f(c):
   lo=max(c['start'],self.loop_start.get());hi=min(c['start']+c['duration'],self.loop_end.get())
   if hi>lo:c['offset']=c.get('offset',0)+lo-c['start'];c['start']=lo;c['duration']=hi-lo
  self.edit(f)
 def move(self):
  p=simpledialog.askfloat('Move','New start time (seconds)',initialvalue=self.position,minvalue=0)
  if p is not None:self.edit(lambda c:c.update(start=p))
 def copy(self):self.edit(lambda c:self.clips.append(dict(c,start=self.position)))
 def clip_gain(self):
  c=self.selected_clip();v=simpledialog.askfloat('Gain','Multiplier',initialvalue=c.get('gain',1),minvalue=0,maxvalue=10) if c else None
  if v is not None:self.edit(lambda c:c.update(gain=v))
 def clip_mute(self):self.edit(lambda c:c.update(mute=not c.get('mute',False)))
 def delete(self):self.edit(lambda c:self.clips.remove(c))
 def draw_mixer(self):
  if not hasattr(self,'mixer'):return
  for child in self.mixer.winfo_children():child.destroy()
  if not self.showmix.get():self.mixer.pack_forget();return
  self.mixer.pack(fill='x',padx=12,pady=(0,10));self.meters={}
  for t in self.tracks[:12]:
   frame=tk.Frame(self.mixer,bg='#303941',width=105);frame.pack(side='left',padx=3,pady=5);frame.pack_propagate(False)
   tk.Label(frame,text=t['name'][:13],bg='#303941',fg=FG,font=('Segoe UI',9)).pack()
   meter=tk.Canvas(frame,width=90,height=52,bg='#e4cf9b',highlightthickness=0);meter.pack(pady=2);meter.create_arc(8,10,82,80,start=25,extent=130,style='arc',outline='#655b44',width=2);needle=meter.create_line(45,45,24,20,fill='#a33e2f',width=2);meter.create_text(45,9,text='VU',font=('Segoe UI',8,'bold'),fill='#3b3325');self.meters[t['id']]=(meter,needle)
   scale=tk.Scale(frame,from_=2,to=0,orient='vertical',resolution=.05,length=85,showvalue=False,bg='#303941',fg=FG,highlightthickness=0,command=lambda val,track=t:track.update(gain=float(val)));scale.set(t['gain']);scale.pack(side='left')
   right=tk.Frame(frame,bg='#303941');right.pack(side='left');tk.Label(right,text='PAN',bg='#303941',fg=FG).pack();pan=tk.Scale(right,from_=-1,to=1,orient='horizontal',resolution=.1,length=55,showvalue=False,bg='#303941',highlightthickness=0,command=lambda val,track=t:track.update(pan=float(val)));pan.set(t['pan']);pan.pack();tk.Label(right,text=f'IN {t["input"]}',bg='#303941',fg=GOLD).pack()
   frame.configure(height=175)
  self.button(self.mixer,'Save mixer',self.save).pack(side='right',padx=10)
 def tick(self):
  if self.running:self.position=self.playhead/RATE;self.draw()
  self.clock.set(f'{int(self.position//60):02}:{self.position%60:05.2f}')
  try:
   while True:
    msg=self.events.get_nowait()
    if msg=='finished':self.stop()
    else:self.status.set(msg)
  except queue.Empty:pass
  self.root.after(100,self.tick)
 def close(self):self.stop();self.save();self.root.destroy()
if __name__=='__main__':
 root=tk.Tk();Studio(root);root.mainloop()
