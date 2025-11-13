import{c as C,j as a,r as s,P as A,g as w,a as p,B as S,F as E,b as n,T as m}from"./index-DHn53uFM.js";const M=C(a.jsx("path",{d:"M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2m-2 15-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8z"}),"CheckCircle"),T=C(a.jsx("path",{d:"M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96M14 13v4h-4v-4H7l5-5 5 5z"}),"CloudUpload"),R=({onFolderDrop:u,onFolderSelect:h,disabled:r=!1,scanning:t=!1})=>{const[o,d]=s.useState(!1),[z,x]=s.useState(0),g=s.useRef(null),k=s.useCallback(e=>{e.preventDefault(),e.stopPropagation(),!(r||t)&&(x(i=>i+1),e.dataTransfer.items&&e.dataTransfer.items.length>0&&d(!0))},[r,t]),v=s.useCallback(e=>{e.preventDefault(),e.stopPropagation(),!(r||t)&&x(i=>{const l=i-1;return l===0&&d(!1),l})},[r,t]),D=s.useCallback(e=>{e.preventDefault(),e.stopPropagation(),!(r||t)&&e.dataTransfer&&(e.dataTransfer.dropEffect="copy")},[r,t]),b=s.useCallback(e=>{if(e.preventDefault(),e.stopPropagation(),d(!1),x(0),r||t)return;const i=Array.from(e.dataTransfer.items);if(i.length>0){const l=i[0];if(l.kind==="file"){const c=l.webkitGetAsEntry();if(c&&c.isDirectory){const f=c.fullPath||c.name;u(f)}else if(c&&c.isFile){const f=l.getAsFile();if(f){const y=f.webkitRelativePath||f.name,P=y.substring(0,y.lastIndexOf("/"))||"./";u(P)}}}}},[r,t,u]),j=s.useCallback(()=>{if(!(r||t)&&h){const e=prompt("Enter folder path to scan:");e&&h(e)}},[r,t,h]);return a.jsxs(A,{ref:g,onDragEnter:k,onDragLeave:v,onDragOver:D,onDrop:b,onClick:j,sx:{position:"relative",p:4,borderRadius:3,border:`2px dashed ${o?"#667eea":t?p(n.text.secondary,.3):p(n.text.disabled,.2)}`,background:o?p("#667eea",.05):t?p(n.background.hover,.5):"transparent",cursor:r||t?"not-allowed":"pointer",transition:"all 0.3s ease",textAlign:"center",overflow:"hidden",opacity:r?.5:1,"&:hover":!r&&!t&&{borderColor:"#667eea",background:p("#667eea",.02),transform:"scale(1.01)"},"&::before":o&&{content:'""',position:"absolute",inset:0,background:w.aurora,opacity:.05,animation:"pulse 2s ease-in-out infinite"},"@keyframes pulse":{"0%, 100%":{opacity:.05},"50%":{opacity:.1}}},children:[a.jsx(S,{sx:{mb:2,display:"flex",justifyContent:"center",alignItems:"center"},children:t?a.jsx(M,{sx:{fontSize:64,color:"#00d4aa",animation:"fadeIn 0.3s ease"}}):o?a.jsx(T,{sx:{fontSize:64,color:"#667eea",animation:"bounce 1s ease infinite"}}):a.jsx(E,{sx:{fontSize:64,color:n.text.disabled,transition:"color 0.3s ease"}})}),a.jsx(m,{variant:"h6",sx:{fontWeight:600,color:o?"#667eea":n.text.primary,mb:1,transition:"color 0.3s ease"},children:t?"Scanning...":o?"Drop folder here":"Drag & Drop Music Folder"}),a.jsx(m,{variant:"body2",sx:{color:n.text.secondary,maxWidth:400,mx:"auto"},children:t?"Please wait while we scan your music library":o?"Release to start scanning":"Drag a folder containing music files here, or click to browse"}),!t&&!o&&a.jsx(m,{variant:"caption",sx:{display:"block",mt:2,color:n.text.disabled,fontSize:11},children:"Supported: MP3, FLAC, WAV, OGG, M4A, AAC, WMA"}),a.jsx("style",{children:`
          @keyframes bounce {
            0%, 100% {
              transform: translateY(0);
            }
            50% {
              transform: translateY(-10px);
            }
          }
          @keyframes fadeIn {
            from {
              opacity: 0;
              transform: scale(0.8);
            }
            to {
              opacity: 1;
              transform: scale(1);
            }
          }
        `})]})};export{R as DropZone};
