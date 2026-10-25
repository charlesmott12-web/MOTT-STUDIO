    c.create_text(x1+5,y+15,text=clip['file'],anchor='w',fill='white',font=('Segoe UI',8))
    try:
     wave=self.audio(clip['file']);ch=min(clip.get('channel',0),wave.shape[1]-1);offset=int(clip.get('offset',0)*RATE);count=int(clip['duration']*RATE);s=wave[offset:offset+count,ch];bins=max(1,int(min(x2-x1,1000)))
     if len(s):
      # Draw the actual minimum and maximum at each screen pixel. Unlike
      # positive-only peaks this shows the shape above and below the axis.
      visible_start=max(0,int((left-x1)/(x2-x1)*len(s))) if x2>x1 else 0
      visible_end=min(len(s),int((w-x1)/(x2-x1)*len(s))+1) if x2>x1 else len(s)
      if visible_end>visible_start:
       first=max(0,int((left-x1)/(x2-x1)*bins)) if x2>x1 else 0
       last=min(bins,int((w-x1)/(x2-x1)*bins)+1) if x2>x1 else bins
       mid=y+self.rowheight/2;scale=max(8,(self.rowheight-27)/2)
       c.create_line(max(left,x1),mid,min(w,x2),mid,fill='#527e89')
       for k in range(first,last):
        a=k*len(s)//bins;b=max(a+1,(k+1)*len(s)//bins)
        seg=s[a:b]
        if len(seg):
         low=float(np.min(seg));high=float(np.max(seg));cx=x1+(k+.5)*(x2-x1)/bins
         c.create_line(cx,mid-high*scale,cx,mid-low*scale,fill='#a5e6de',width=1)
    except Exception:pass
  px=left+self.position*self.zoom;c.create_line(px,0,px,max(100,len(self.tracks)*self.rowheight+28),fill='#f0b45d',width=2)
  c.configure(scrollregion=(0,0,w,max(300,28+len(self.tracks)*self.rowheight)))
 def click(self,e):
  row=int((e.y-28)//self.rowheight)
  if not 0<=row<len(self.tracks):return
  t=self.tracks[row];y=e.y-(28+row*self.rowheight)
  if e.x<210:
   if 40<=y<=70:
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
  self.mixer.pack(fill='x',padx=12,pady=(0,10));self.meters={};self.input_widgets={}
  for t in self.tracks[:12]:
   frame=tk.Frame(self.mixer,bg='#303941',width=105);frame.pack(side='left',padx=3,pady=5);frame.pack_propagate(False)
   tk.Label(frame,text=t['name'][:13],bg='#303941',fg=FG,font=('Segoe UI',9)).pack()
   meter=tk.Canvas(frame,width=90,height=52,bg='#e4cf9b',highlightthickness=0);meter.pack(pady=2);meter.create_arc(8,10,82,80,start=25,extent=130,style='arc',outline='#655b44',width=2);needle=meter.create_line(45,45,24,20,fill='#a33e2f',width=2);meter.create_text(45,9,text='VU',font=('Segoe UI',8,'bold'),fill='#3b3325');self.meters[t['id']]=(meter,needle)
   scale=tk.Scale(frame,from_=2,to=0,orient='vertical',resolution=.05,length=85,showvalue=False,bg='#303941',fg=FG,highlightthickness=0,command=lambda val,track=t:track.update(gain=float(val)));scale.set(t['gain']);scale.pack(side='left')
   right=tk.Frame(frame,bg='#303941');right.pack(side='left');tk.Label(right,text='PAN',bg='#303941',fg=FG).pack();pan=tk.Scale(right,from_=-1,to=1,orient='horizontal',resolution=.1,length=55,showvalue=False,bg='#303941',highlightthickness=0,command=lambda val,track=t:track.update(pan=float(val)));pan.set(t['pan']);pan.pack();tk.Label(right,text='INPUT',bg='#303941',fg=GOLD).pack()
   input_var=tk.StringVar(value=f'{t.get("input",1)} - Input {t.get("input",1)}')
   combo=ttk.Combobox(right,textvariable=input_var,values=['1 - Input 1','2 - Input 2'],state='readonly',width=11)
   combo.pack();combo.bind('<<ComboboxSelected>>',lambda e,track=t,var=input_var:self.set_input(track,var.get()));self.input_widgets[t['id']]=combo
   frame.configure(height=175)
  self.button(self.mixer,'Save mixer',self.save).pack(side='right',padx=10)
 def tick(self):
  if self.running:self.position=self.playhead/RATE;self.draw()
  self.clock.set(f'{int(self.position//60):02}:{self.position%60:05.2f}')
  # Tk widgets are updated here on the GUI thread, never from PortAudio.
  for tid,(canvas,needle) in tuple(self.meters.items()):
   level=self.live_levels.get(tid,0.0) if self.running else 0.0
   old=self.meter_smoothed.get(tid,0.0)
   smooth=old+(level-old)*(0.53 if level>old else 0.19)
   self.meter_smoothed[tid]=smooth
   # RMS amplitude mapped to analog-style dB range, with a quiet resting stop.
   db=20*math.log10(max(1e-7,smooth))
   fraction=max(0.,min(1.,(db+48.)/48.))
   angle=math.radians(155.-130.*fraction)
   canvas.coords(needle,45,46,45+33*math.cos(angle),46-33*math.sin(angle))
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
