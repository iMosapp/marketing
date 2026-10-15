/* i'M On Social - social ad phone player. Poster + gold play; plays with sound on tap. */
(function(){
  function setup(box){
    var video=box.querySelector('video');
    var screen=box.querySelector('.ad-screen');
    var playBtn=box.querySelector('.ad-play');
    var icon=playBtn?playBtn.querySelector('i'):null;
    if(!video||!screen||!playBtn) return;
    function start(){
      if(video.ended||video.currentTime>=video.duration-0.25){video.currentTime=0}
      video.muted=false;
      video.controls=true;
      box.classList.remove('ended');
      box.classList.add('playing');
      var p=video.play();
      if(p&&p.catch){p.catch(function(){box.classList.remove('playing');video.controls=false})}
      if(window.gtag&&!box.dataset.tracked){box.dataset.tracked='1';try{window.gtag('event','video_play',{video_title:'social_ad_sept_8',page_path:location.pathname})}catch(e){}}
    }
    playBtn.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();start()});
    screen.addEventListener('click',function(e){if(!box.classList.contains('playing')){start()}});
    video.addEventListener('pause',function(){
      if(video.ended) return;
      box.classList.remove('playing');
      video.controls=false;
      if(icon){icon.className='fa-solid fa-play'}
    });
    video.addEventListener('play',function(){box.classList.add('playing');video.controls=true});
    video.addEventListener('ended',function(){
      box.classList.remove('playing');
      box.classList.add('ended');
      video.controls=false;
      if(icon){icon.className='fa-solid fa-rotate-right'}
    });
    // Pause other ad players on the page when one starts
    video.addEventListener('play',function(){
      document.querySelectorAll('.ad-phone video').forEach(function(v){if(v!==video&&!v.paused){v.pause()}});
    });
  }
  function init(){document.querySelectorAll('.ad-phone').forEach(setup)}
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init)}else{init()}
})();
