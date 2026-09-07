import {Marked} from "./vendor/marked.mjs";
export const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function safeURL(value) {
  try {
    const url=new URL(value);
    return ["https:","http:"].includes(url.protocol)&&!url.username&&!url.password?url.href:null;
  }catch{return null;}
}
const parser=new Marked({
  gfm:true,
  renderer:{
    html({text}){return escapeHTML(text);},
    link({href,tokens}){
      const label=this.parser.parseInline(tokens),url=safeURL(href);
      return url?'<a href="'+escapeHTML(url)+'" target="_blank" rel="noopener noreferrer">'+label+"</a>":label;
    },
    image({href,text}){
      const url=safeURL(href);
      return url?'<a href="'+escapeHTML(url)+'" target="_blank" rel="noopener noreferrer">'+escapeHTML(text||"参考图片")+"</a>":escapeHTML(text);
    }
  }
});
export function markdown(text,sources=[]){
  let source=String(text||"");
  // Reference definitions allow source IDs to resolve without rewriting arbitrary HTML.
  const refs=sources.filter(s=>/^S\d+$/.test(s.id)&&safeURL(s.url)).map(s=>"["+s.id+"]: <"+safeURL(s.url).replace(/>/g,"%3E")+">").join("\n");
  source+="\n\n"+refs;
  return parser.parse(source).replace(/<table>/g,'<div class="table-wrap"><table>').replace(/<\/table>/g,"</table></div>");
}
