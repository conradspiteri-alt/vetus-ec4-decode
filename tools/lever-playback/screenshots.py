import asyncio, sys
from playwright.async_api import async_playwright
import os
HERE=os.path.dirname(os.path.abspath(__file__))
HTML='file://'+os.path.join(HERE,'dist','EC4-Lever-Playback.html')
OUT=os.path.join(HERE,'..','..','docs','images','events')+os.sep
SHOTS=[(105.30,'01-power-on'),(287.50,'02-command-taken-warm-up'),(299.70,'03-warm-up-off'),
       (317.35,'04-starboard-ahead-engaged'),(356.30,'05-starboard-throttle-49pc'),(485.60,'06-port-fast-reversal-shifting'),
       (486.10,'07-port-astern-engaged'),(522.50,'08-starboard-reversal-throttle-to-idle'),(523.12,'09-starboard-astern-engaged')]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={'width':1400,'height':1320}, device_scale_factor=1, color_scheme='light')
        await pg.goto(HTML); await pg.wait_for_timeout(1500)
        for t,name in SHOTS:
            await pg.evaluate("t=>{const s=document.getElementById('scrub'); s.value=t; s.dispatchEvent(new Event('input',{bubbles:true}));}", t)
            await pg.wait_for_timeout(300)
            got=await pg.evaluate("document.documentElement.dataset.playT")
            await pg.screenshot(path=OUT+name+'.png', clip={'x':110,'y':0,'width':1180,'height':1290})
            print(name, t, got)
        await b.close()
asyncio.run(main())
