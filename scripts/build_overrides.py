"""Hand-written (human) French and Swahili text for the advice bundle + disease-name glossary.

Why: NLLB mistranslates domain terms (it rendered "Late blight" as "early pain" in Swahili). So
  * disease NAMES come from this glossary (never from MT),
  * French + Swahili sentences are written by a person here and win over MT (translation_overrides.json),
  * rw / rn / so / yo still use NLLB and are labelled "machine translated" until native speakers add overrides.

Run:  python scripts/build_overrides.py   ->  artifacts/translation_overrides.json
(These two languages still deserve a native proof-read before public release.)
"""
import json
from pathlib import Path

ART = Path(__file__).resolve().parents[1] / "artifacts"

# English sentence -> (French, Swahili)
S = {
 "Act today.": ("Agissez dès aujourd'hui.", "Chukua hatua leo."),
 "Avoid wounding the tree.": ("Évitez de blesser l'arbre.", "Epuka kuumiza mti."),
 "Check your plants every week.": ("Vérifiez vos plantes chaque semaine.", "Kagua mimea yako kila wiki."),
 "Control the small jumping insects on your citrus trees.": ("Luttez contre les petits insectes sauteurs sur vos agrumes.", "Dhibiti wadudu wadogo warukao kwenye miti yako ya machungwa."),
 "Control whiteflies with yellow sticky traps or neem oil.": ("Combattez les aleurodes avec des pièges collants jaunes ou de l'huile de neem.", "Dhibiti nzi weupe kwa mitego ya manjano yenye gundi au mafuta ya mwarobaini."),
 "Cover big cuts with a wound paste.": ("Couvrez les grosses coupes avec un mastic cicatrisant.", "Funika sehemu kubwa zilizokatwa kwa dawa ya kufunga vidonda vya mti."),
 "Cover seedbeds with a net.": ("Couvrez les pépinières avec un filet.", "Funika vitalu vya miche kwa chandarua."),
 "Cover the soil with mulch.": ("Couvrez le sol avec du paillis.", "Funika udongo kwa matandazo."),
 "Cut off and burn the badly affected shoots.": ("Coupez et brûlez les pousses gravement atteintes.", "Kata na uchome machipukizi yaliyoathirika vibaya."),
 "Cut out dead branches and burn them.": ("Coupez les branches mortes et brûlez-les.", "Kata matawi yaliyokufa na uyachome."),
 "Cut out the dead wood in dry weather and burn it.": ("Coupez le bois mort par temps sec et brûlez-le.", "Kata sehemu zilizokufa za mti wakati wa hali kavu na uzichome."),
 "Do not kill the helpful insects.": ("Ne tuez pas les insectes utiles.", "Usiue wadudu wenye manufaa."),
 "Do not let plants suffer from dust or dry soil.": ("Ne laissez pas les plantes souffrir de la poussière ou de la sécheresse du sol.", "Usiache mimea iteseke kwa vumbi au udongo mkavu."),
 "Do not plant maize in the same field every year.": ("Ne plantez pas du maïs dans le même champ chaque année.", "Usipande mahindi katika shamba moja kila mwaka."),
 "Do not plant peppers in the same place for two or three years.": ("Ne plantez pas de poivrons au même endroit pendant deux ou trois ans.", "Usipande pilipili hoho mahali pamoja kwa miaka miwili au mitatu."),
 "Do not plant potatoes in the same field every year.": ("Ne plantez pas de pommes de terre dans le même champ chaque année.", "Usipande viazi katika shamba moja kila mwaka."),
 "Do not plant tomatoes in the same place for two or three years.": ("Ne plantez pas de tomates au même endroit pendant deux ou trois ans.", "Usipande nyanya mahali pamoja kwa miaka miwili au mitatu."),
 "Do not plant tomatoes or potatoes in the same place every year.": ("Ne plantez pas de tomates ou de pommes de terre au même endroit chaque année.", "Usipande nyanya au viazi mahali pamoja kila mwaka."),
 "Do not plant too close together.": ("Ne plantez pas trop serré.", "Usipande karibu mno."),
 "Do not spray in the hot midday sun.": ("Ne pulvérisez pas en plein soleil de midi.", "Usinyunyizie wakati wa jua kali la mchana."),
 "Do not store tubers that look sick.": ("Ne stockez pas les tubercules qui semblent malades.", "Usihifadhi viazi vinavyoonekana vimeugua."),
 "Do not touch the plants when they are wet.": ("Ne touchez pas les plantes quand elles sont mouillées.", "Usiguse mimea ikiwa imelowa."),
 "Do not use too much nitrogen fertilizer.": ("N'utilisez pas trop d'engrais azoté.", "Usitumie mbolea ya naitrojeni nyingi mno."),
 "Do not water over the leaves.": ("N'arrosez pas sur les feuilles.", "Usimwagilie maji juu ya majani."),
 "Feed the plants well.": ("Nourrissez bien les plantes.", "Lisha mimea vizuri."),
 "Feed the trees well.": ("Nourrissez bien les arbres.", "Lisha miti vizuri."),
 "Give the plants space.": ("Laissez de l'espace entre les plantes.", "Acha nafasi kati ya mimea."),
 "Heap soil on the rows to cover the tubers.": ("Buttez les rangs pour couvrir les tubercules.", "Rundikia udongo kwenye mistari ili kufunika viazi."),
 "Hold the phone close to one leaf.": ("Approchez le téléphone d'une seule feuille.", "Weka simu karibu na jani moja."),
 "I am not sure.": ("Je n'en suis pas sûr.", "Sina uhakika."),
 "If rust is heavy before the tassel appears, spray a fungicide. Follow the label.": ("Si la rouille est forte avant l'apparition des panicules, pulvérisez un fongicide. Suivez l'étiquette.", "Kama kutu ni nyingi kabla maua ya kiume hayajatoka, nyunyizia dawa ya kuua kuvu. Fuata maelekezo kwenye lebo."),
 "If the problem gets worse, ask your agriculture officer or agro-dealer for help.": ("Si le problème s'aggrave, demandez de l'aide à votre agent agricole ou à votre vendeur d'intrants.", "Tatizo likiongezeka, muulize afisa kilimo au muuza pembejeo akusaidie."),
 "If the spots keep spreading, spray a fungicide that is approved for this crop. Follow the label.": ("Si les taches continuent de s'étendre, pulvérisez un fongicide autorisé pour cette culture. Suivez l'étiquette.", "Madoa yakiendelea kuenea, nyunyizia dawa ya kuua kuvu iliyoidhinishwa kwa zao hili. Fuata maelekezo kwenye lebo."),
 "It makes a white powder on the leaves.": ("Il forme une poudre blanche sur les feuilles.", "Husababisha unga mweupe kwenye majani."),
 "It makes big dark wet patches on the leaves and white mold in damp weather.": ("Il forme de grandes taches sombres et humides sur les feuilles et un duvet blanc par temps humide.", "Husababisha mabaka makubwa meusi yenye unyevu kwenye majani na ukungu mweupe wakati wa unyevu."),
 "It makes bright yellow-orange spots on the leaves.": ("Il forme des taches jaune orangé vif sur les feuilles.", "Husababisha madoa ya manjano-machungwa angavu kwenye majani."),
 "It makes brown leaf spots with a purple edge and rots the fruit.": ("Il forme des taches brunes à bord violet sur les feuilles et fait pourrir les fruits.", "Husababisha madoa ya kahawia yenye ukingo wa zambarau kwenye majani na huoza matunda."),
 "It makes brown round spots with black dots, and the grapes dry up black.": ("Il forme des taches rondes brunes avec des points noirs, et les raisins se dessèchent en noir.", "Husababisha madoa ya kahawia ya duara yenye vitone vyeusi, na zabibu hukauka na kuwa nyeusi."),
 "It makes brown spots with rings on the leaves and sometimes on the fruit.": ("Il forme des taches brunes avec des anneaux sur les feuilles et parfois sur les fruits.", "Husababisha madoa ya kahawia yenye pete kwenye majani na wakati mwingine kwenye matunda."),
 "It makes brown spots with rings, like a target, first on the old lower leaves.": ("Il forme des taches brunes avec des anneaux, comme une cible, d'abord sur les vieilles feuilles du bas.", "Husababisha madoa ya kahawia yenye pete kama shabaha, kwanza kwenye majani ya chini ya zamani."),
 "It makes dark brown spots with straight edges on the leaves.": ("Il forme des taches brun foncé aux bords anguleux sur les feuilles.", "Husababisha madoa ya kahawia iliyokolea yenye kingo zilizonyooka kwenye majani."),
 "It makes dark olive-green to black rough spots on leaves and fruit.": ("Il forme des taches rugueuses vert olive foncé à noires sur les feuilles et les fruits.", "Husababisha madoa magumu ya kijani-mzeituni iliyokolea hadi nyeusi kwenye majani na matunda."),
 "It makes dark wet patches on the leaves and white mold under the leaf when it is damp. It can destroy the field in a few days.": ("Il forme des taches sombres et humides sur les feuilles et un duvet blanc sous la feuille quand il fait humide. Il peut détruire le champ en quelques jours.", "Husababisha mabaka meusi yenye unyevu kwenye majani na ukungu mweupe chini ya jani wakati wa unyevu. Unaweza kuharibu shamba zima ndani ya siku chache."),
 "It makes long gray-brown rectangular spots on the leaves.": ("Il forme de longues taches rectangulaires gris-brun sur les feuilles.", "Husababisha madoa marefu ya mstatili ya rangi ya kijivu-kahawia kwenye majani."),
 "It makes long gray-green spots shaped like cigars.": ("Il forme de longues taches gris-vert en forme de cigare.", "Husababisha madoa marefu ya kijivu-kijani yenye umbo la sigara."),
 "It makes many small round spots with a gray center on the lower leaves.": ("Il forme de nombreuses petites taches rondes à centre gris sur les feuilles du bas.", "Husababisha madoa mengi madogo ya duara yenye kituo cha kijivu kwenye majani ya chini."),
 "It makes pale yellow spots on top of the leaf and olive-brown mold under the leaf.": ("Il forme des taches jaune pâle sur le dessus de la feuille et un duvet brun olive sous la feuille.", "Husababisha madoa ya manjano hafifu juu ya jani na ukungu wa kahawia-mzeituni chini ya jani."),
 "It makes small dark spots on the leaves and fruit, and holes in the leaves.": ("Il forme de petites taches sombres sur les feuilles et les fruits, et des trous dans les feuilles.", "Husababisha madoa madogo meusi kwenye majani na matunda, na mashimo kwenye majani."),
 "It makes small dark spots with a yellow ring on the leaves and rough spots on the fruit.": ("Il forme de petites taches sombres entourées d'un anneau jaune sur les feuilles et des taches rugueuses sur les fruits.", "Husababisha madoa madogo meusi yenye pete ya manjano kwenye majani na madoa magumu kwenye matunda."),
 "It makes small dark wet-looking spots on the leaves and fruit.": ("Il forme de petites taches sombres d'aspect mouillé sur les feuilles et les fruits.", "Husababisha madoa madogo meusi yanayoonekana kuwa na unyevu kwenye majani na matunda."),
 "It makes small purple spots that join together and the leaf edges look burnt.": ("Il forme de petites taches violettes qui se rejoignent, et les bords des feuilles semblent brûlés.", "Husababisha madoa madogo ya zambarau yanayoungana, na kingo za majani huonekana kama zimeungua."),
 "It makes small round red-brown bumps on both sides of the leaf.": ("Il forme de petites pustules rondes brun-rouge sur les deux faces de la feuille.", "Husababisha vipele vidogo vya duara vya rangi ya kahawia-nyekundu pande zote mbili za jani."),
 "It makes yellow-orange powder spots under the leaf, and then the leaves fall.": ("Il forme des taches poudreuses jaune orangé sous la feuille, puis les feuilles tombent.", "Husababisha madoa ya unga wa manjano-machungwa chini ya jani, kisha majani huanguka."),
 "It makes many small round spots with a gray center on the lower leaves.": ("Il forme de nombreuses petites taches rondes à centre gris sur les feuilles du bas.", "Husababisha madoa mengi madogo ya duara yenye kituo cha kijivu kwenye majani ya chini."),
 "Keep dust away from the trees.": ("Éloignez la poussière des arbres.", "Zuia vumbi lisifike kwenye miti."),
 "Keep the ground clean under the vines.": ("Gardez le sol propre sous les vignes.", "Weka ardhi safi chini ya mizabibu."),
 "Keep the leaf in the center.": ("Gardez la feuille au centre.", "Weka jani katikati."),
 "Keep the leaves dry.": ("Gardez les feuilles sèches.", "Weka majani yakiwa makavu."),
 "Keep the vineyard clean.": ("Gardez le vignoble propre.", "Weka shamba la zabibu safi."),
 "Keep weeds away.": ("Éloignez les mauvaises herbes.", "Ondoa magugu."),
 "Light rust usually does not need treatment.": ("Une rouille légère n'a généralement pas besoin de traitement.", "Kutu kidogo kwa kawaida hakuhitaji matibabu."),
 "No disease was seen.": ("Aucune maladie n'a été vue.", "Hakuna ugonjwa uliogunduliwa."),
 "No treatment is needed.": ("Aucun traitement n'est nécessaire.", "Hakuna matibabu yanayohitajika."),
 "Open the greenhouse or space the plants so air can pass.": ("Aérez la serre ou espacez les plantes pour laisser passer l'air.", "Fungua chafu au acha nafasi kati ya mimea ili hewa ipite."),
 "Pick up and burn fallen leaves and spotted leaves.": ("Ramassez et brûlez les feuilles tombées et les feuilles tachetées.", "Okota na uchome majani yaliyoanguka na yenye madoa."),
 "Plant certified clean seed potatoes.": ("Plantez des plants de pommes de terre certifiés sains.", "Panda mbegu za viazi zilizothibitishwa kuwa safi."),
 "Plant early in the season.": ("Plantez tôt dans la saison.", "Panda mapema katika msimu."),
 "Plant in full sun.": ("Plantez en plein soleil.", "Panda mahali penye jua la kutosha."),
 "Plant only clean, certified seedlings.": ("Plantez uniquement des plants sains et certifiés.", "Panda miche safi iliyothibitishwa tu."),
 "Plant resistant apple varieties.": ("Plantez des variétés de pommiers résistantes.", "Panda aina za tufaha zinazostahimili ugonjwa."),
 "Plant resistant seed.": ("Plantez des semences résistantes.", "Panda mbegu zinazostahimili ugonjwa."),
 "Plant resistant varieties.": ("Plantez des variétés résistantes.", "Panda aina zinazostahimili ugonjwa."),
 "Plant scab-resistant varieties.": ("Plantez des variétés résistantes à la tavelure.", "Panda aina zinazostahimili kigaga."),
 "Please take the photo again in good light with one leaf in the center.": ("Veuillez reprendre la photo avec une bonne lumière et une seule feuille au centre.", "Tafadhali piga picha tena mahali penye mwanga mzuri, ukiweka jani moja katikati."),
 "Please take the photo again.": ("Veuillez reprendre la photo.", "Tafadhali piga picha tena."),
 "Prune only in dry weather.": ("Taillez uniquement par temps sec.", "Pogoa wakati wa hali kavu tu."),
 "Prune so air and sun reach the leaves.": ("Taillez pour que l'air et le soleil atteignent les feuilles.", "Pogoa ili hewa na jua vifike kwenye majani."),
 "Prune so air can pass through.": ("Taillez pour laisser passer l'air.", "Pogoa ili hewa ipite."),
 "Prune the coffee and the shade trees so air can pass through.": ("Taillez les caféiers et les arbres d'ombrage pour laisser passer l'air.", "Pogoa kahawa na miti ya kivuli ili hewa ipite."),
 "Prune the tree so air can pass through.": ("Taillez l'arbre pour laisser passer l'air.", "Pogoa mti ili hewa ipite."),
 "Pull out and burn sick plants.": ("Arrachez et brûlez les plantes malades.", "Ng'oa na uchome mimea iliyougua."),
 "Pull out and destroy sick plants early.": ("Arrachez et détruisez tôt les plantes malades.", "Ng'oa na uharibu mimea iliyougua mapema."),
 "Pull out and destroy the sick plants.": ("Arrachez et détruisez les plantes malades.", "Ng'oa na uharibu mimea iliyougua."),
 "Pull out and destroy the sick plants. Do not leave them in the field.": ("Arrachez et détruisez les plantes malades. Ne les laissez pas au champ.", "Ng'oa na uharibu mimea iliyougua. Usiiache shambani."),
 "Remove and burn badly sick plants.": ("Retirez et brûlez les plantes gravement malades.", "Ondoa na uchome mimea iliyougua vibaya."),
 "Remove and burn the sick tree. Tell your agriculture officer.": ("Retirez et brûlez l'arbre malade. Prévenez votre agent agricole.", "Ondoa na uchome mti uliougua. Mwambie afisa kilimo wako."),
 "Remove and bury the badly sick leaves.": ("Retirez et enterrez les feuilles très malades.", "Ondoa na uzike majani yaliyougua vibaya."),
 "Remove dried grapes and spotted leaves and burn them.": ("Retirez les raisins desséchés et les feuilles tachetées et brûlez-les.", "Ondoa zabibu zilizokauka na majani yenye madoa kisha uyachome."),
 "Remove juniper or cedar trees growing nearby.": ("Retirez les genévriers ou cèdres qui poussent à proximité.", "Ondoa miti ya mreteni au mwerezi inayokua karibu."),
 "Remove or bury old maize stalks after harvest.": ("Retirez ou enterrez les vieilles tiges de maïs après la récolte.", "Ondoa au uzike mabua ya mahindi ya zamani baada ya mavuno."),
 "Remove or bury the old maize stalks after harvest.": ("Retirez ou enterrez les vieilles tiges de maïs après la récolte.", "Ondoa au uzike mabua ya mahindi ya zamani baada ya mavuno."),
 "Remove rotten and dried fruit from the tree and the ground.": ("Retirez les fruits pourris et desséchés de l'arbre et du sol.", "Ondoa matunda yaliyooza na kukauka kutoka kwenye mti na ardhini."),
 "Remove spotted leaves.": ("Retirez les feuilles tachetées.", "Ondoa majani yenye madoa."),
 "Remove the sick leaves.": ("Retirez les feuilles malades.", "Ondoa majani yaliyougua."),
 "Remove the spotted leaves.": ("Retirez les feuilles tachetées.", "Ondoa majani yenye madoa."),
 "Remove the spotted lower leaves.": ("Retirez les feuilles tachetées du bas.", "Ondoa majani ya chini yenye madoa."),
 "Remove the worst leaves and fruit.": ("Retirez les feuilles et les fruits les plus atteints.", "Ondoa majani na matunda yaliyoathirika zaidi."),
 "Remove the worst leaves.": ("Retirez les feuilles les plus atteintes.", "Ondoa majani yaliyoathirika zaidi."),
 "Replace old plants.": ("Remplacez les vieilles plantes.", "Badilisha mimea ya zamani."),
 "Rotate maize with beans or other crops.": ("Alternez le maïs avec des haricots ou d'autres cultures.", "Zungusha mahindi na maharage au mazao mengine."),
 "Rotate potatoes with other crops.": ("Alternez les pommes de terre avec d'autres cultures.", "Zungusha viazi na mazao mengine."),
 "Rotate tomatoes with other crops.": ("Alternez les tomates avec d'autres cultures.", "Zungusha nyanya na mazao mengine."),
 "Space the plants.": ("Espacez les plantes.", "Acha nafasi kati ya mimea."),
 "Spray a copper fungicide as the label says.": ("Pulvérisez un fongicide à base de cuivre selon l'étiquette.", "Nyunyizia dawa ya kuua kuvu yenye shaba kama lebo inavyoelekeza."),
 "Spray a copper product as the label says.": ("Pulvérisez un produit à base de cuivre selon l'étiquette.", "Nyunyizia dawa yenye shaba kama lebo inavyoelekeza."),
 "Spray a fungicide approved for potatoes. Follow the label.": ("Pulvérisez un fongicide autorisé pour la pomme de terre. Suivez l'étiquette.", "Nyunyizia dawa ya kuua kuvu iliyoidhinishwa kwa viazi. Fuata maelekezo kwenye lebo."),
 "Spray a fungicide approved for tomatoes. Follow the label.": ("Pulvérisez un fongicide autorisé pour la tomate. Suivez l'étiquette.", "Nyunyizia dawa ya kuua kuvu iliyoidhinishwa kwa nyanya. Fuata maelekezo kwenye lebo."),
 "Spray soap water or neem oil on the underside of the leaves.": ("Pulvérisez de l'eau savonneuse ou de l'huile de neem sous les feuilles.", "Nyunyizia maji ya sabuni au mafuta ya mwarobaini chini ya majani."),
 "Spray sulphur as the label says.": ("Pulvérisez du soufre selon l'étiquette.", "Nyunyizia salfa kama lebo inavyoelekeza."),
 "Spray sulphur or neem oil as the label says.": ("Pulvérisez du soufre ou de l'huile de neem selon l'étiquette.", "Nyunyizia salfa au mafuta ya mwarobaini kama lebo inavyoelekeza."),
 "Spray water under the leaves.": ("Pulvérisez de l'eau sous les feuilles.", "Nyunyizia maji chini ya majani."),
 "Stake the plants.": ("Tuteurez les plantes.", "Weka vigingi vya kusaidia mimea."),
 "The leaf looks healthy.": ("La feuille semble en bonne santé.", "Jani linaonekana lina afya."),
 "The leaves curl up, turn yellow and stay small, and the plant stops growing.": ("Les feuilles s'enroulent, jaunissent et restent petites, et la plante arrête de grandir.", "Majani hujikunja, huwa ya manjano na hubaki madogo, na mmea huacha kukua."),
 "The leaves get small yellow dots and fine webs.": ("Les feuilles se couvrent de petits points jaunes et de fines toiles.", "Majani hupata vitone vidogo vya manjano na utando mwembamba."),
 "The leaves get yellow and red stripes between the veins.": ("Les feuilles présentent des bandes jaunes et rouges entre les nervures.", "Majani hupata mistari ya manjano na nyekundu kati ya mishipa."),
 "The leaves get yellow patches and the fruit stays small, bitter and lopsided.": ("Les feuilles ont des plages jaunes et les fruits restent petits, amers et déformés.", "Majani hupata mabaka ya manjano na matunda hubaki madogo, machungu na yasiyo na umbo sawa."),
 "The leaves show light and dark green patches and look twisted.": ("Les feuilles montrent des plages vert clair et vert foncé et semblent déformées.", "Majani huonyesha mabaka ya kijani kibichi hafifu na iliyokolea na huonekana yamepindika."),
 "The leaves turn bronze or reddish, mostly in dry and dusty weather.": ("Les feuilles deviennent bronze ou rougeâtres, surtout par temps sec et poussiéreux.", "Majani huwa ya rangi ya shaba au nyekundu kiasi, hasa wakati wa hali kavu yenye vumbi."),
 "There is no cure.": ("Il n'existe pas de remède.", "Hakuna tiba."),
 "These are tiny insects under the leaf.": ("Ce sont de minuscules insectes sous la feuille.", "Hawa ni wadudu wadogo sana chini ya jani."),
 "This disease is caused by bacteria.": ("Cette maladie est causée par des bactéries.", "Ugonjwa huu husababishwa na bakteria."),
 "This does not look like a plant leaf.": ("Cela ne ressemble pas à une feuille de plante.", "Hili halionekani kama jani la mmea."),
 "This is a fungus that likes damp, closed places.": ("C'est un champignon qui aime les endroits humides et fermés.", "Huu ni kuvu unaopenda maeneo yenye unyevu na yaliyofungwa."),
 "This is a fungus that lives in the wood of the vine.": ("C'est un champignon qui vit dans le bois de la vigne.", "Huu ni kuvu unaoishi kwenye mti wa mzabibu."),
 "This is a fungus.": ("C'est un champignon.", "Huu ni kuvu."),
 "This is a guide only.": ("Ceci n'est qu'un guide.", "Huu ni mwongozo tu."),
 "This is a serious disease spread by a small insect.": ("C'est une maladie grave transmise par un petit insecte.", "Huu ni ugonjwa mbaya unaoenezwa na mdudu mdogo."),
 "This is a very fast and dangerous fungus.": ("C'est un champignon très rapide et dangereux.", "Huu ni kuvu hatari unaoenea haraka sana."),
 "This is a virus spread by whiteflies.": ("C'est un virus transmis par les aleurodes (mouches blanches).", "Huu ni virusi vinavyoenezwa na nzi weupe."),
 "This is a virus.": ("C'est un virus.", "Hivi ni virusi."),
 "Use a miticide only if it is really needed. Follow the label.": ("Utilisez un acaricide seulement si c'est vraiment nécessaire. Suivez l'étiquette.", "Tumia dawa ya kuua utitiri tu ikiwa kweli inahitajika. Fuata maelekezo kwenye lebo."),
 "Use clean seed.": ("Utilisez des semences saines.", "Tumia mbegu safi."),
 "Use clean tools.": ("Utilisez des outils propres.", "Tumia vifaa safi."),
 "Use daylight.": ("Utilisez la lumière du jour.", "Tumia mwanga wa mchana."),
 "Use resistant seed.": ("Utilisez des semences résistantes.", "Tumia mbegu zinazostahimili ugonjwa."),
 "Use resistant varieties.": ("Utilisez des variétés résistantes.", "Tumia aina zinazostahimili ugonjwa."),
 "Wash your hands and tools with soap after touching sick plants.": ("Lavez-vous les mains et les outils avec du savon après avoir touché des plantes malades.", "Osha mikono na vifaa vyako kwa sabuni baada ya kugusa mimea iliyougua."),
 "Wash your hands before touching the plants.": ("Lavez-vous les mains avant de toucher les plantes.", "Osha mikono kabla ya kugusa mimea."),
 "Watch your trees for the small insects.": ("Surveillez vos arbres pour repérer les petits insectes.", "Angalia miti yako kama ina wadudu wadogo."),
 "Water at the base of the plant.": ("Arrosez au pied de la plante.", "Mwagilia maji chini ya mmea."),
}

# label -> (English, French, Swahili) display names. English term is kept in brackets for Swahili so that
# extension officers recognise it. rw/rn/so/yo show the English name (no machine translation of disease names).
N = {
 "apple___apple_scab": ("Apple scab", "Tavelure du pommier", "Kigaga cha tufaha (Apple scab)"),
 "apple___black_rot": ("Black rot", "Pourriture noire", "Uozo mweusi (Black rot)"),
 "apple___cedar_apple_rust": ("Cedar apple rust", "Rouille grillagée du pommier", "Kutu ya tufaha (Cedar apple rust)"),
 "cherry___powdery_mildew": ("Powdery mildew", "Oïdium", "Ukungu wa unga (Powdery mildew)"),
 "maize___cercospora_leaf_spot_gray_leaf_spot": ("Gray leaf spot", "Cercosporiose (tache grise)", "Madoa ya kijivu ya majani (Gray leaf spot)"),
 "maize___common_rust": ("Common rust", "Rouille commune", "Kutu ya kawaida (Common rust)"),
 "maize___northern_leaf_blight": ("Northern leaf blight", "Helminthosporiose du nord", "Kuungua kwa majani (Northern leaf blight)"),
 "grape___black_rot": ("Black rot", "Pourriture noire (black rot)", "Uozo mweusi (Black rot)"),
 "grape___esca_black_measles": ("Esca (black measles)", "Esca (maladie du bois)", "Esca (ugonjwa wa mti wa mzabibu)"),
 "grape___leaf_blight_isariopsis_leaf_spot": ("Leaf blight (Isariopsis)", "Brûlure des feuilles (Isariopsis)", "Kuungua kwa majani ya zabibu (Isariopsis)"),
 "orange___haunglongbing_citrus_greening": ("Citrus greening (HLB)", "Huanglongbing (greening des agrumes)", "Ugonjwa wa kuwa kijani wa machungwa (Citrus greening, HLB)"),
 "peach___bacterial_spot": ("Bacterial spot", "Tache bactérienne", "Madoa ya bakteria (Bacterial spot)"),
 "pepper___bacterial_spot": ("Bacterial spot", "Tache bactérienne", "Madoa ya bakteria (Bacterial spot)"),
 "potato___early_blight": ("Early blight", "Alternariose (brûlure précoce)", "Baka la majani la mapema (Early blight)"),
 "potato___late_blight": ("Late blight", "Mildiou", "Baka la majani la kuchelewa (Late blight)"),
 "squash___powdery_mildew": ("Powdery mildew", "Oïdium", "Ukungu wa unga (Powdery mildew)"),
 "strawberry___leaf_scorch": ("Leaf scorch", "Brûlure des feuilles", "Kuungua kwa majani (Leaf scorch)"),
 "tomato___bacterial_spot": ("Bacterial spot", "Tache bactérienne", "Madoa ya bakteria (Bacterial spot)"),
 "tomato___early_blight": ("Early blight", "Alternariose (brûlure précoce)", "Baka la majani la mapema (Early blight)"),
 "tomato___late_blight": ("Late blight", "Mildiou", "Baka la majani la kuchelewa (Late blight)"),
 "tomato___leaf_mold": ("Leaf mold", "Cladosporiose (moisissure des feuilles)", "Ukungu wa majani (Leaf mold)"),
 "tomato___septoria_leaf_spot": ("Septoria leaf spot", "Septoriose", "Madoa ya majani ya Septoria"),
 "tomato___spider_mites_two_spotted_spider_mite": ("Spider mites", "Acariens (araignées rouges)", "Utitiri wa buibui (Spider mites)"),
 "tomato___target_spot": ("Target spot", "Tache cible (corynesporiose)", "Madoa ya pete (Target spot)"),
 "tomato___tomato_yellow_leaf_curl_virus": ("Yellow leaf curl virus", "Virus de l'enroulement jaune en cuillère (TYLCV)", "Virusi vya kujikunja kwa majani ya manjano (TYLCV)"),
 "tomato___tomato_mosaic_virus": ("Tomato mosaic virus", "Virus de la mosaïque de la tomate", "Virusi vya mosaiki ya nyanya"),
 "coffee___rust": ("Coffee leaf rust", "Rouille du caféier", "Kutu ya majani ya kahawa (Coffee leaf rust)"),
 "coffee___red_spider_mite": ("Red spider mite", "Araignée rouge (acarien)", "Utitiri mwekundu (Red spider mite)"),
}
HEALTHY = ("Healthy", "En bonne santé", "Una afya")

def load_indexed(code):
    """Hand-written languages beyond fr/sw: scripts/human/advice_<code>.py (index|text lines + names + crop names)."""
    import importlib.util
    en = [l.split("|", 1)[1] for l in (ART.parent / "scripts" / "human" / "_en_sentences.txt").read_text(encoding="utf-8").splitlines()]
    spec = importlib.util.spec_from_file_location(f"advice_{code}", ART.parent / "scripts" / "human" / f"advice_{code}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    lines = {}
    for ln in m.LINES.splitlines():
        i, t = ln.split("|", 1)
        lines[int(i)] = t.strip()
    miss = [i for i in range(len(en)) if i not in lines]
    assert not miss, f"{code}: missing sentence indexes {miss}"
    return {en[i]: lines[i] for i in range(len(en))}, m.NAMES, m.CROPS


if __name__ == "__main__":
    out = {"fr": {k: v[0] for k, v in S.items()}, "sw": {k: v[1] for k, v in S.items()}, "_names": {"en": {}, "fr": {}, "sw": {}}, "_crops": {}}
    for code in ("es", "pt", "hi", "ar"):
        sent, names, crops = load_indexed(code)
        assert set(sent) == set(S), f"{code}: sentence set differs from the knowledge base"
        out[code] = sent; out["_names"][code] = names; out["_crops"][code] = crops
    for lab, (en, fr, sw) in N.items():
        out["_names"]["en"][lab], out["_names"]["fr"][lab], out["_names"]["sw"][lab] = en, fr, sw
    for i, lg in enumerate(("en", "fr", "sw")):
        out["_names"][lg]["healthy"] = HEALTHY[i]
    for code in ("es", "pt", "hi", "ar"):
        for lab in N:      # every disease label must have a hand-written name
            assert lab in out["_names"][code], f"{code}: no name for {lab}"
    ART.mkdir(exist_ok=True)
    (ART / "translation_overrides.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("overrides:", len(S), "sentences x fr/sw;", len(N), "disease names")
