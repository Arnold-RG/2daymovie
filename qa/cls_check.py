"""First-screen layout-shift check (manual / CI helper).

python qa/cls_check.py URL [WIDTH HEIGHT]   env DELAY_MS (default 2500) delays data/*.json like a slow network.
Exits 1 if the summed layout shift is above 0.05 (Lighthouse "good" is < 0.1)."""
import asyncio, sys, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width":int(sys.argv[2]) if len(sys.argv)>2 else 412,"height":int(sys.argv[3]) if len(sys.argv)>3 else 823}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await ctx.add_init_script("""window.__cls=[];new PerformanceObserver(l=>{for(const e of l.getEntries()){if(e.hadRecentInput)continue;window.__cls.push({v:+e.value.toFixed(4),t:Math.round(e.startTime),src:(e.sources||[]).map(s=>{const n=s.node;return [n?(n.id||n.className||n.tagName)+'':'?', Math.round(s.previousRect.y), Math.round(s.currentRect.y), Math.round(s.previousRect.height), Math.round(s.currentRect.height)]}).slice(0,4)})}}).observe({type:'layout-shift',buffered:true});
        window.__lcp=[];new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lcp.push({t:Math.round(e.startTime),el:e.element&&(e.element.className||e.element.tagName),url:(e.url||"").slice(-40),size:e.size})}).observe({type:'largest-contentful-paint',buffered:true});""")
        import os
        delay = int(os.environ.get("DELAY_MS", "2500"))
        if delay:
            async def slow(route):
                await asyncio.sleep(delay / 1000); await route.continue_()
            await ctx.route("**/data/*.json", slow)
        pg = await ctx.new_page(); await pg.goto(sys.argv[1], wait_until="load"); await pg.wait_for_timeout(6000)
        r = await pg.evaluate("() => ({cls: window.__cls.reduce((a,e)=>a+e.v,0).toFixed(3), shifts: window.__cls.slice(0,12), lcp: window.__lcp})")
        print(json.dumps(r, indent=1)); await b.close()
        if float(r["cls"]) > 0.05: sys.exit(1)
asyncio.run(main())
