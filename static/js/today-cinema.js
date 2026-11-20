"use strict";
document.addEventListener("DOMContentLoaded",()=>{
  const host=document.getElementById("tm-feature-player");
  const trigger=host&&host.querySelector("[data-tm-video]");
  if(!trigger)return;
  trigger.addEventListener("click",()=>{
    const id=trigger.dataset.tmVideo||"";
    const title=trigger.dataset.tmTitle||"movie";
    if(!/^[A-Za-z0-9_-]{11}$/.test(id)){
      const note=document.createElement("p");note.className="tm-preview-error";note.textContent="This preview is not available right now.";
      host.replaceChildren(note);return;
    }
    const frame=document.createElement("iframe");
    frame.src="https://www.youtube-nocookie.com/embed/"+encodeURIComponent(id)+"?autoplay=1&playsinline=1";
    frame.title="Official trailer: "+title;
    frame.referrerPolicy="strict-origin-when-cross-origin";
    frame.allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
    frame.allowFullscreen=true;
    host.replaceChildren(frame);
  },{once:true});
});