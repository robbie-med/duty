/* The welcome and the About page, in the four languages of the site. */
const ABOUT = {
  en: {
    title: "About",
    welcome: ["Welcome. You are not alone.",
      "Whatever your ancestry, and however mixed, your forebears lived on this earth with the knowledge of God and of eternity written in them.",
      "All truth is God’s truth.",
      "Jesus has shown us the true meaning of the law.",
      "Over centuries and millennia, peoples have built ways of keeping families together and in connection, loving one another. Their writings still hold those ways.",
      "Read in the clear light of Scripture, with the illumination of the Holy Spirit, they help us love our families better.",
      "The Way sets out the moral duties we owe one another, and where each is taught."],
    enter: "Enter",
    tradHead: "The traditions",
    tradIntro: "Where they differ, they are weighed in this order.",
    traditions: [
      ["Scripture", "The Old and New Testaments. Every other source is weighed against them."],
      ["Westminster", "The Confession of Faith and the Larger and Shorter Catechisms of the Westminster Assembly (1640s), the standards of Presbyterian churches. The Larger Catechism sets out the duties of every relation under the Fifth Commandment."],
      ["Puritan", "English and Scottish pastors of the sixteenth and seventeenth centuries, among them William Perkins, William Gouge, Richard Baxter and Matthew Henry, who wrote at length on the duties of the household; with them John Calvin, and their heirs into the nineteenth century."],
      ["English custom", "The law and household custom of England: Blackstone’s Commentaries, the Book of Common Prayer and the Homilies, the Poor Laws, and the customs of inheritance."],
      ["New England", "The laws of the Massachusetts, Plymouth and Vermont colonies, and the sermons of their pastors, such as Thomas Cobbet and Samuel Willard."],
      ["Catholic", "Papal teaching on marriage and the family from Leo XIII (1880) onward, the Catechism of the Catholic Church, and canon law."],
      ["Modern Reformed", "Reformed writers of the twentieth and twenty-first centuries."],
      ["Classical", "Greek and Roman writing on the household: Xenophon, Aristotle, Cicero."],
      ["Confucian", "The Chinese classics and the family instructions built on them: the Analects, the Mencius, the Book of Rites, Sima Guang’s Family Norms, Zhu Xi’s Family Rituals (twelfth century), and the rules of lineages."],
      ["Korean custom", "The family customs of the Joseon dynasty (1392–1910): Yi I’s Gyeongmong Yogyeol, the Elementary Learning in Korean, Queen Sohye’s Instructions for Women, the books of rites and the law codes."],
      ["Our house", "The rules a family sets for itself. They come last, and are judged by all the rest."]],
    histHead: "Christians and the Chinese rites",
    history: [
      "In 1583 the Jesuit Matteo Ricci entered China. He judged the honors Chinese families paid to Confucius and to their ancestors to be civil rather than religious, and let Chinese Christians keep them.",
      "Dominican and Franciscan missionaries disagreed, and the question went to Rome. In 1700 the Kangxi Emperor declared the rites civil. Pope Clement XI forbade them in 1704 and again in 1715, and Benedict XIV confirmed the ban in 1742.",
      "In 1939 Pius XII allowed Catholics to take part in ceremonies honoring Confucius and the dead, as civil customs.",
      "Protestant missionaries met in Shanghai in 1890. W. A. P. Martin, a Presbyterian who had then lived in China for forty years, pleaded for toleration: the heart of ancestral worship, he argued, was filial love, and the church should reform it from within rather than forbid it. The conference recorded its dissent, affirming “that idolatry is an essential constituent of ancestral worship.”",
      "In 1907 the Centenary Conference again held the worship of ancestors incompatible with the Christian faith, yet urged care “not to destroy in our Christian converts the feeling of reverence for the dead which this custom seeks to express.”",
      "In Korea in 1791, Paul Yun Ji-chung buried his mother with Christian rites and burned the family’s ancestral tablets; he and his cousin James Kwon Sang-yeon were executed. Korean Protestant churches came to keep the remembrance of the dead in services of worship and thanksgiving (추도예배) in place of the rites.",
      "The question has always been the same: which honors to parents and forebears belong to the Fifth Commandment, and which give to the dead what belongs to God alone."]
  },
  ko: {
    title: "소개",
    welcome: ["환영합니다. 당신은 혼자가 아닙니다.",
      "당신의 혈통이 어떠하든, 얼마나 섞였든, 당신의 조상들은 하나님과 영원에 대한 앎을 지닌 채 이 땅에서 살았습니다.",
      "모든 진리는 하나님의 진리입니다.",
      "예수께서 율법의 참뜻을 우리에게 보여 주셨습니다.",
      "수 세기, 수천 년에 걸쳐 여러 민족은 가족이 함께하며 서로 이어지고 사랑하도록 하는 길을 세워 왔습니다. 그들의 글에는 그 길이 지금도 남아 있습니다.",
      "성경의 밝은 빛 아래, 성령의 조명하심 가운데 읽을 때, 그 글들은 우리가 가족을 더 잘 사랑하도록 돕습니다.",
      "도(道)는 우리가 서로에게 지는 도덕적 도리와, 각 도리가 어디에서 가르쳐지는지를 밝힙니다."],
    enter: "들어가기",
    tradHead: "전통들",
    tradIntro: "서로 다를 때에는 이 순서로 무게를 둡니다.",
    traditions: [
      ["성경", "구약과 신약. 다른 모든 자료는 성경에 비추어 판단합니다."],
      ["웨스트민스터", "웨스트민스터 총회(1640년대)의 신앙고백과 대·소요리문답으로, 장로교회의 표준 문서입니다. 대요리문답은 제5계명 아래 모든 관계의 도리를 설명합니다."],
      ["청교도", "16–17세기 잉글랜드와 스코틀랜드의 목회자들로, 윌리엄 퍼킨스, 윌리엄 구지, 리처드 백스터, 매튜 헨리 등이 가정의 도리에 관해 깊이 썼습니다. 장 칼뱅과 19세기까지 이어진 그 후계자들도 함께 다룹니다."],
      ["영국 관습", "잉글랜드의 법과 가정 관습: 블랙스톤의 『영국법 주해』, 공동기도서와 설교집, 구빈법, 상속 관습."],
      ["뉴잉글랜드", "매사추세츠, 플리머스, 버몬트 식민지의 법률과, 토머스 코벳과 새뮤얼 윌러드 같은 목회자들의 설교."],
      ["가톨릭", "레오 13세(1880) 이후 혼인과 가정에 관한 교황의 가르침, 『가톨릭 교회 교리서』, 교회법."],
      ["현대 개혁주의", "20세기와 21세기의 개혁주의 저술가들."],
      ["고전", "가정에 관한 그리스와 로마의 저술: 크세노폰, 아리스토텔레스, 키케로."],
      ["유교", "중국 고전과 그 위에 세워진 가훈들: 『논어』, 『맹자』, 『예기』, 사마광의 『가범』, 주희의 『가례』(12세기), 그리고 종족의 규약."],
      ["한국 관습", "조선(1392–1910)의 가정 관습: 이이의 『격몽요결』, 『소학언해』, 소혜왕후의 『내훈』, 예서(禮書)와 법전."],
      ["우리 집안", "한 가족이 스스로 정한 규칙. 맨 마지막에 오며, 다른 모든 전통에 비추어 판단합니다."]],
    histHead: "그리스도인과 중국의 예식",
    history: [
      "1583년 예수회의 마테오 리치가 중국에 들어갔습니다. 그는 중국 가정이 공자와 조상에게 드리는 예를 종교가 아닌 시민적 예절로 보았고, 중국 그리스도인들이 이를 지키도록 허용했습니다.",
      "도미니코회와 프란치스코회 선교사들은 이에 반대했고, 문제는 로마로 넘어갔습니다. 1700년 강희제는 이 예식이 시민적인 것이라고 선언했습니다. 교황 클레멘스 11세는 1704년과 1715년에 이를 금지했고, 베네딕토 14세는 1742년에 그 금지를 확정했습니다.",
      "1939년 비오 12세는 공자와 고인을 기리는 의식을 시민적 관습으로서 가톨릭 신자들이 참여할 수 있도록 허락했습니다.",
      "1890년 개신교 선교사들이 상하이에 모였습니다. 당시 중국에서 40년을 지낸 장로교 선교사 W. A. P. 마틴(丁韙良)은 관용을 호소했습니다. 그는 조상 숭배의 핵심이 효심이므로 교회가 이를 금하기보다 안에서부터 고쳐 가야 한다고 주장했습니다. 대회는 반대 의견을 기록하며 “우상 숭배는 조상 숭배의 본질적 요소”라고 확언했습니다.",
      "1907년 100주년 선교대회는 다시 조상 숭배가 그리스도교 신앙과 양립할 수 없다고 보았지만, “이 관습이 표현하려는 고인에 대한 경외의 마음을 그리스도인 개종자들 안에서 없애지 않도록” 주의하라고 권했습니다.",
      "조선에서는 1791년 윤지충 바오로가 어머니를 그리스도교 예식으로 장사하고 집안의 신주를 불살랐고, 그와 외사촌 권상연 야고보는 처형되었습니다. 한국 개신교회는 제사 대신 예배와 감사의 추도예배로 고인을 기억하게 되었습니다.",
      "질문은 언제나 같았습니다. 부모와 조상에게 드리는 공경 가운데 무엇이 제5계명에 속하며, 무엇이 오직 하나님께 속한 것을 죽은 이에게 드리는 것인가."]
  },
  "zh-Hant": {
    title: "關於",
    welcome: ["歡迎。你並不孤單。",
      "無論你的祖源如何、多麼交錯，你的先人都曾在這地上生活，心中刻著對神與永恆的認識。",
      "凡真理都是神的真理。",
      "耶穌向我們顯明了律法的真義。",
      "千百年來，各民族建立了使家人團聚、彼此相連、相親相愛的方法。他們的著作至今仍保存著這些方法。",
      "在聖經明亮的光中、藉著聖靈的光照來讀，這些著作幫助我們更好地愛我們的家人。",
      "道列出我們彼此當盡的道德本分，以及每一項本分出自何處的教導。"],
    enter: "進入",
    tradHead: "各傳統",
    tradIntro: "彼此不同時，依此順序衡量輕重。",
    traditions: [
      ["聖經", "舊約與新約。其他一切來源都以聖經衡量。"],
      ["西敏", "西敏會議（1640年代）的《信仰告白》與《大、小要理問答》，是長老會的信仰標準。《大要理問答》在第五誡之下闡明各種關係的本分。"],
      ["清教徒", "十六、十七世紀英格蘭與蘇格蘭的牧者，如威廉·帕金斯、威廉·古奇、理查·巴克斯特、馬太·亨利，詳論家庭的本分；並包括約翰·加爾文，以及延續至十九世紀的承繼者。"],
      ["英國習俗", "英格蘭的法律與家庭習俗：布萊克斯通的《英格蘭法釋義》、《公禱書》與《講道集》、濟貧法，以及繼承的習俗。"],
      ["新英格蘭", "麻薩諸塞、普利茅斯與佛蒙特殖民地的法律，以及湯瑪斯·科貝特、撒母耳·威拉德等牧者的講道。"],
      ["天主教", "自良十三世（1880年）以來教宗關於婚姻與家庭的訓導、《天主教教理》與教會法典。"],
      ["現代改革宗", "二十與二十一世紀的改革宗著作者。"],
      ["古典", "希臘與羅馬論家政的著作：色諾芬、亞里斯多德、西塞羅。"],
      ["儒家", "中國經典及以之為本的家訓：《論語》、《孟子》、《禮記》、司馬光《家範》、朱熹《家禮》（十二世紀），以及宗族規約。"],
      ["韓國習俗", "朝鮮王朝（1392–1910）的家庭習俗：李珥《擊蒙要訣》、《小學諺解》、昭惠王后《內訓》、禮書與法典。"],
      ["本家", "一個家族為自己所定的規矩。列於最後，並以其他一切傳統來衡量。"]],
    histHead: "基督徒與中國禮儀",
    history: [
      "1583年，耶穌會士利瑪竇進入中國。他認為中國家庭敬孔祭祖之禮屬於世俗禮節而非宗教，准許中國基督徒保留。",
      "道明會與方濟會的傳教士不以為然，爭議遂送至羅馬。1700年，康熙帝宣告這些禮儀屬於世俗。教宗克萊孟十一世於1704年與1715年禁止，本篤十四世於1742年確認此禁令。",
      "1939年，庇護十二世准許天主教徒以世俗禮俗的身分參與尊孔與追念亡者的儀式。",
      "1890年，基督教新教傳教士在上海集會。當時已在中國生活四十年的長老會傳教士丁韙良（W. A. P. Martin）呼籲寬容：他主張祭祖的核心是孝心，教會應從內部加以改革，而非禁止。大會記錄了反對意見，確認「偶像崇拜是祭祖的本質成分」。",
      "1907年的百年傳教大會再次認定祭祖與基督信仰不能相容，但勸勉要謹慎，「不要摧毀我們基督徒信眾心中這習俗所要表達的對亡者的敬重之情」。",
      "在朝鮮，1791年尹持忠（保祿）以基督教禮儀安葬母親，並焚燒家中神主牌；他與表兄弟權尚然（雅各伯）遭處決。韓國新教教會後來以敬拜與感恩的追悼禮拜（추도예배）紀念亡者，取代祭祀。",
      "問題始終如一：對父母與先人的尊敬，哪些屬於第五誡，哪些是把唯獨屬於神的歸給了死人。"]
  },
  "zh-Hans": {
    title: "关于",
    welcome: ["欢迎。你并不孤单。",
      "无论你的祖源如何、多么交错，你的先人都曾在这地上生活，心中刻着对神与永恒的认识。",
      "凡真理都是神的真理。",
      "耶稣向我们显明了律法的真义。",
      "千百年来，各民族建立了使家人团聚、彼此相连、相亲相爱的方法。他们的著作至今仍保存着这些方法。",
      "在圣经明亮的光中、借着圣灵的光照来读，这些著作帮助我们更好地爱我们的家人。",
      "道列出我们彼此当尽的道德本分，以及每一项本分出自何处的教导。"],
    enter: "进入",
    tradHead: "各传统",
    tradIntro: "彼此不同时，依此顺序衡量轻重。",
    traditions: [
      ["圣经", "旧约与新约。其他一切来源都以圣经衡量。"],
      ["西敏", "西敏会议（1640年代）的《信仰告白》与《大、小要理问答》，是长老会的信仰标准。《大要理问答》在第五诫之下阐明各种关系的本分。"],
      ["清教徒", "十六、十七世纪英格兰与苏格兰的牧者，如威廉·帕金斯、威廉·古奇、理查德·巴克斯特、马太·亨利，详论家庭的本分；并包括约翰·加尔文，以及延续至十九世纪的承继者。"],
      ["英国习俗", "英格兰的法律与家庭习俗：布莱克斯通的《英格兰法释义》、《公祷书》与《讲道集》、济贫法，以及继承的习俗。"],
      ["新英格兰", "马萨诸塞、普利茅斯与佛蒙特殖民地的法律，以及托马斯·科贝特、塞缪尔·威拉德等牧者的讲道。"],
      ["天主教", "自良十三世（1880年）以来教宗关于婚姻与家庭的训导、《天主教教理》与教会法典。"],
      ["现代改革宗", "二十与二十一世纪的改革宗著作者。"],
      ["古典", "希腊与罗马论家政的著作：色诺芬、亚里士多德、西塞罗。"],
      ["儒家", "中国经典及以之为本的家训：《论语》、《孟子》、《礼记》、司马光《家范》、朱熹《家礼》（十二世纪），以及宗族规约。"],
      ["韩国习俗", "朝鲜王朝（1392–1910）的家庭习俗：李珥《击蒙要诀》、《小学谚解》、昭惠王后《内训》、礼书与法典。"],
      ["本家", "一个家族为自己所定的规矩。列于最后，并以其他一切传统来衡量。"]],
    histHead: "基督徒与中国礼仪",
    history: [
      "1583年，耶稣会士利玛窦进入中国。他认为中国家庭敬孔祭祖之礼属于世俗礼节而非宗教，准许中国基督徒保留。",
      "多明我会与方济各会的传教士不以为然，争议遂送至罗马。1700年，康熙帝宣告这些礼仪属于世俗。教宗克雷芒十一世于1704年与1715年禁止，本笃十四世于1742年确认此禁令。",
      "1939年，庇护十二世准许天主教徒以世俗礼俗的身份参与尊孔与追念亡者的仪式。",
      "1890年，基督教新教传教士在上海集会。当时已在中国生活四十年的长老会传教士丁韪良（W. A. P. Martin）呼吁宽容：他主张祭祖的核心是孝心，教会应从内部加以改革，而非禁止。大会记录了反对意见，确认“偶像崇拜是祭祖的本质成分”。",
      "1907年的百年传教大会再次认定祭祖与基督信仰不能相容，但劝勉要谨慎，“不要摧毁我们基督徒信众心中这习俗所要表达的对亡者的敬重之情”。",
      "在朝鲜，1791年尹持忠（保禄）以基督教礼仪安葬母亲，并焚烧家中神主牌；他与表兄弟权尚然（雅各伯）遭处决。韩国新教教会后来以敬拜与感恩的追悼礼拜（추도예배）纪念亡者，取代祭祀。",
      "问题始终如一：对父母与先人的尊敬，哪些属于第五诫，哪些是把唯独属于神的归给了死人。"]
  }
};
const aboutText = () => ABOUT[LANG] || ABOUT.en;
/* the About page: the welcome, the traditions in their order, and the history of the rites */
function aboutHTML() {
  const A = aboutText();
  return `<div class="about">${A.welcome.map((p, i) => `<p${i === 0 ? ' class="lead"' : ""}>${p}</p>`).join("")}
    <h3>${A.tradHead}</h3><p class="mute">${A.tradIntro}</p>
    <dl>${A.traditions.map(([n, d]) => `<dt>${n}</dt><dd>${d}</dd>`).join("")}</dl>
    <h3>${A.histHead}</h3>${A.history.map(p => `<p>${p}</p>`).join("")}</div>`;
}
/* the welcome, once per browser, before the site */
function maybeWelcome() {
  let seen = false;
  try { seen = localStorage.getItem("way-welcomed") === "1"; } catch (e) { /* private window */ }
  if (seen || document.getElementById("welcome")) return;
  const A = aboutText();
  document.body.insertAdjacentHTML("beforeend", `<div id="welcome" role="dialog" aria-modal="true" style="position:fixed;inset:0;z-index:9999;background:rgba(30,24,16,.55);display:flex;align-items:center;justify-content:center;padding:16px">
    <div style="max-width:560px;width:100%;max-height:90vh;overflow:auto;background:#fffdf8;border-radius:14px;padding:28px 26px;box-shadow:0 10px 40px rgba(0,0,0,.3);font-size:16px;line-height:1.55">
      <div style="text-align:center;font-size:30px;color:#8a2a1a;margin-bottom:6px">道</div>
      ${A.welcome.map((p, i) => `<p style="margin:0 0 12px${i === 0 ? ";font-size:20px;font-weight:600;text-align:center" : ""}">${p}</p>`).join("")}
      <div style="display:flex;gap:8px;justify-content:center;align-items:center;margin-top:16px;flex-wrap:wrap">
        <select onchange="setLang(this.value).then(()=>{document.getElementById('welcome').remove();maybeWelcome()})" style="padding:8px">${langOptions()}</select>
        <button class="btn pri" style="padding:10px 26px;font-size:16px" onclick="try{localStorage.setItem('way-welcomed','1')}catch(e){};document.getElementById('welcome').remove()">${A.enter}</button></div></div></div>`);
}
