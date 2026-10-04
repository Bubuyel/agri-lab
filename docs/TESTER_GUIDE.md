# Agri Lab – tester guide (share this with your testers)

**What you are testing:** a farm helper that works **without internet**. It has three parts:

1. 📷 **Check my plant** – take a photo of ONE leaf. The app tells you the plant, whether it is healthy or sick, what to do and how to prevent it, in your language.
2. 💰 **Crop prices** – choose your place and a crop: price now, expected price for the next 6 months, best month to sell, markets near you, other currencies.
3. 🌧️ **Rain outlook** – will the next 3 months be wetter or drier than usual at your place?

## Install (once, with internet, ~10 MB)
1. Open the link you were given in **Chrome**.
2. Wait until the home screen shows **"Ready: works without internet"**.
3. Chrome menu ⋮ → **Install app** (or *Add to Home screen*).
4. Try it with the phone in **airplane mode**.

## Please try these 8 things
| # | Test | What should happen |
|---|---|---|
| 1 | Change the language in ⚙️ | All text changes. **Tell us any word that looks wrong.** |
| 2 | Photo of a **tomato / potato / maize / coffee / pepper** leaf in daylight | Correct plant name, sensible advice |
| 3 | Photo of a **hand, floor, phone, a person** | "This is not a plant leaf" + ask to retake |
| 4 | Photo of a **cassava, banana or bean** leaf | The app should say **"Not in our data yet"** with a probability bar (tell us if it names a disease instead) |
| 5 | A blurry or dark leaf photo | "I am not sure, take another photo" (not a confident wrong answer) |
| 6 | Prices → choose your place → your main crop | Price is close to what you see at the market? Is the forecast sensible? |
| 7 | Rain → your place | Do the "usual rain" numbers match your experience of the seasons? |
| 8 | Airplane mode, close and reopen the app | Everything still works |

## What to send us (WhatsApp / form)
* Phone model and Android version
* For each wrong plant answer: a screenshot (photos stay on your phone; the app never uploads anything)
* Is the advice understandable for a farmer? Which sentence was confusing?
* Price: crop, place, what the app said vs the real market price
* Anything slow, ugly or confusing (how many seconds did the photo take?)

## Good to know
* The advice is a **guide**, not a doctor. For serious problems ask your agriculture officer.
* Only these plants are supported today: apple, blueberry, cherry, coffee, grape, maize, orange, peach, pepper, potato, raspberry, soybean, squash, strawberry, tomato.
* Prices come from WFP market surveys and are national medians – a forecast is a guess based on past prices.
* 16 languages are included. English, French, Spanish, Portuguese, Arabic, Hindi and Swahili are written by people; Kinyarwanda, Kirundi, Somali, Yoruba, Hausa, Igbo, Amharic, Oromo and Tigrinya are **machine translated (beta)** and shown with a warning – your corrections are very welcome.
* **Camera:** on the real (https) site "Take photo" opens a live view that unlocks the shutter only when it sees a plant in good light. Over plain http it falls back to the phone camera.
* **Listen** buttons appear only when the phone has a voice for the chosen language (no voice packs are bundled, to keep the app small).
* The model is wrong more often on field photos (~72% crop, ~59% disease) than on clean ones (~92% / ~85%). Plants it has never seen (e.g. mango) can still be mistaken for a supported crop.
