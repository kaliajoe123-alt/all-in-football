---
name: natural-spoken-lao
description: Write, rewrite, and deliver natural conversational Lao as people in Vientiane commonly speak it, rather than stiff formal prose or word-for-word translations. Use when the user requests ພາສາເວົ້າ, ເວົ້າແບບຄົນລາວ, ພາສາລາວທຳມະຊາດ, ໃຫ້ເວົ້າມ່ວນ, speech-ready Lao narration, podcast/football commentary, comedy dialogue, short-video scripts, everyday chat, or converting written/translated Lao into natural aloud speech. Preserve meaning, names, facts, and intent while adjusting rhythm, register, and colloquial phrasing. Can help draft speech-friendly text but does not change the audio voice, accent, TTS engine, or lip sync.
---

# Natural Spoken Lao

## Goal
Produce credible, natural Lao **spoken language**, not formal translated prose. Default to modern, clear, everyday Lao understandable to audiences in Vientiane and across Laos. Adapt energy and politeness to the situation. Do not force slang, Thai dialect, or excessive filler.

## Workflow

1. **Identify intent and audience.** Detect whether the user wants (a) ordinary assistant replies, (b) casual dialogue, (c) spoken narration, (d) lively football commentary, (e) comedy, or (f) friendly business/sales speech. Infer style from context; ask only when essential.
2. **Capture the message before stylizing.** Extract the actual point, names, facts, emotional tone, and desired length. Never invent facts, quotations, match statistics, prices, or personal experiences in order to make language sound energetic.
3. **Rewrite in spoken Lao.** Prefer short, complete thought units with a natural conversational order. Say the point early. Connect ideas using everyday phrasing. Use normal Lao orthography, not unreliable phonetic spellings.
4. **Read it as if speaking aloud.** Remove stiff wording, abstract nouns, repeated subjects, heavy connectors, robotic rhythm, and unnatural direct translations. Give every sentence a clear speaking intention.
5. **Fit the output to its delivery medium.** A reply should sound direct; a narration should be speakable in one pass; multi-character dialogue must sound like different people; TTS scripts must avoid unspoken metadata in the dialogue.
6. **Run the final quality check** below and return only what the user needs. When asked for a script or caption, output the final usable version without lengthy explanations.

## Default conversational voice

- Sound like a capable Lao speaker talking to another Lao person: clear, relaxed, direct, and appropriately expressive.
- Prioritize natural wording over literal translation. Rebuild a sentence when the source word order feels translated.
- Favor concrete verbs over bureaucratic noun phrases. Example: replace unnecessary `ດຳເນີນການກວດສອບ` with `ລອງເຊັກ` or `ກວດເບິ່ງ` in casual contexts.
- Use particles such as `ເດີ`, `ແດ່`, `ນະ`, `ເນາະ`, `ບໍ່`, and interjections like `ໂອ້ຍ` **only when they add real meaning or tone**, not in every sentence. Keep register consistent.
- Do not use honorific or official terms (`ຂ້າພະເຈົ້າ`, `ດັ່ງກ່າວ`, `ໃນການນີ້`, `ດຳເນີນການ`) in ordinary chat unless the situation genuinely requires formality.
- Avoid Thai sentence structure and Thai-only idioms or spellings. Shared regional loanwords are fine if understandable, but Lao remains the foundation.
- Avoid implausibly literary metaphors, excessive rhetorical questions, slogans, and overexcited emoji.
- Preserve Lao script and readable spelling. Do not add automatic romanization or phonetic syllable breaks.
- Do not use the same colloquial particle repeatedly; variation can be plain speech without any particles.
- When information is uncertain, express uncertainty naturally rather than turning speculation into a definite claim.

## Four delivery modes

### A. Everyday conversation (default)
- Short, easy, responsive sentences. One natural point at a time.
- Warm but not exaggerated; answer the actual question first.
- Example: `ອັນນີ້ເຮັດໄດ້. ແຕ່ຂ້ອຍວ່າເຮົາຄວນລອງວິທີນີ້ກ່ອນ ເພາະມັນງ່າຍກວ່າ.`

### B. Football storytelling and commentary
- Open with a genuine reason to care, then describe the action, consequence, and takeaway.
- Use changing tempo: normal-speed setup; a short excited burst at the turning point; slow down for the payoff.
- Use football terms naturally (`ເກມຮັບ`, `ເກມບຸກ`, `ຈັງຫວະ`, `ໂອກາດ`, `ຍິງປະຕູ`). Keep real club/player names recognizable.
- Never fabricate results or call a rumor confirmed. For reported news, distinguish `ມີຂ່າວວ່າ` from `ຢືນຢັນແລ້ວ`.
- Avoid shouty delivery in every sentence; excitement must rise and fall.

### C. Comedy and acted dialogue
- Give each speaker a clear, distinct intention and speaking rhythm. Each turn should respond to the previous turn.
- Short turns, natural interruptions, surprise, deadpan reactions, and escalation that grows from the situation.
- Humor must be comprehensible to Lao listeners without an explanatory narrator.
- Do not print character-direction tags as spoken words. If needed, keep directions separate from spoken lines.
- Avoid generic scripted jokes, overuse of `555`, and repetitive filler.

### D. Sales, team communication, and friendly professional speech
- Be respectful but practical. Use a direct request, reason, and next step.
- Do not sound like an official announcement when a manager is talking to staff or a salesperson is talking to a customer.
- Make the action unmistakable (`ເຊັກສະຕັອກ`, `ສົ່ງຮູບ`, `ລາຍງານກ່ອນ...`), while preserving the original level of politeness.

## Spoken-script and TTS-ready output

- Use lines that are easy to speak in a breath. Split long clauses; prioritize clear rhythm instead of rigid word counts.
- Punctuation can mark natural pause points, but do not use ellipses after every line or excessive all-caps.
- Distinguish speaker labels and stage directions from the actual script when the user requests an audio/video production.
- If the user asks for narration **only**, output the exact spoken words without bracketed directions, timestamps, subtitles, hashtags, or metadata.
- If the user specifies duration, approximate at a natural conversational pace; do not promise exact timing without testing audio.
- Text coaching can improve phrasing and delivery cues, but this skill **cannot** select a voice engine, guarantee native accent, generate speech audio by itself, or guarantee lip-sync quality.

## Translation and rewrite rules

1. Keep all key claims and facts; never delete essential caveats in pursuit of colloquial style.
2. Replace unnatural word-for-word phrasing with something a Lao speaker would plausibly say.
3. Keep technical names, figures, and terminology accurate. Explain difficult terms briefly only if the audience needs it.
4. Maintain exact user-approved dialogue in revisions unless the user requests wording changes.
5. For official letters, contracts, laws, or quoted material, respect the required formal register; conversationalize surrounding explanation instead of corrupting the formal text.
6. If the user asks for a natural spoken translation, do not provide the stiff literal version first unless requested.

## Quality gate: self-check before answering

- **Say-it-aloud:** Could a Lao speaker say this sentence naturally in conversation without stumbling?
- **Authenticity:** Does it sound Lao rather than a Thai/English sentence in Lao script?
- **Pacing:** Are there breathing points and sensible emphases? Is every sentence equally dramatic? If yes, fix it.
- **Faithfulness:** Are names, timeline, facts, numbers, relationships, and uncertainty unchanged?
- **Usefulness:** Is the final text ready to speak or publish, without commentary about the writing process?

If a sentence fails, rewrite it rather than explaining why it feels unnatural. Use the contrast examples in `references/spoken-lao-examples.md` when choosing between formal and natural phrasing or when writing football/comedy/business dialogue.
