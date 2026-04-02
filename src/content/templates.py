"""LinkedIn post templates — hook patterns and post structures."""


HOOK_TEMPLATES = {
    "surprising_stat": [
        "Most people don't realize that {stat}. That single number tells you everything about where {market} is headed.",
        "{stat}. Let that sink in for a moment. The {market} is sending a signal that very few are paying attention to.",
        "Here's a number that should be on every trader's radar: {stat}. And yet, almost nobody is talking about it.",
    ],
    "provocative_question": [
        "What happens when {scenario}? We might be about to find out.",
        "If {commodity} prices {direction} by {amount} tomorrow, who wins and who loses? The answer might surprise you.",
        "Why is everyone talking about {topic_a} when the real story is {topic_b}?",
    ],
    "bold_claim": [
        "The {market} is fundamentally mispriced right now. Here's why that matters for everyone in the supply chain.",
        "We are witnessing the biggest shift in {market} in a decade, and most people haven't noticed yet.",
        "{market} will never be the same after this. The changes happening right now are structural, not cyclical.",
    ],
    "personal_observation": [
        "I've been tracking {market} for years, and what I'm seeing right now is genuinely unusual.",
        "A conversation with a {role} last week completely changed how I think about {topic}.",
        "Something interesting happened in {market} this week that flew under the radar of most analysts.",
    ],
    "current_event_reference": [
        "{event} just changed the equation for {market}. Here's what it means going forward.",
        "The news about {event} is bigger than most people think. Let me explain why {market} participants should care.",
        "Everyone is reacting to {event}, but they're missing the second-order effects on {market}.",
    ],
    "contrarian_take": [
        "The consensus on {market} is wrong. Here's the data that tells a different story.",
        "Everyone says {common_belief}. But the supply chain data tells a completely different story.",
        "I know this is an unpopular take, but {contrarian_view}. And the numbers back it up.",
    ],
}


CTA_TEMPLATES = [
    "What's your read on this? I'd love to hear from anyone working in {market} right now.",
    "If you're in the {market} space, what are you seeing on the ground? Drop your thoughts below.",
    "Do you agree, or am I missing something? Let me know in the comments.",
    "What's the biggest risk here that nobody is talking about? I'm curious what this community thinks.",
    "How is this affecting your business or portfolio? I'd genuinely like to know.",
    "If you found this useful, share it with someone in your network who needs to see this.",
]


POST_STRUCTURES = {
    "insight": {
        "description": "Share a non-obvious insight about the market",
        "flow": [
            "hook (surprising stat or observation)",
            "context paragraph (what's happening)",
            "insight paragraph (the non-obvious takeaway)",
            "implication paragraph (why it matters)",
            "cta (invite discussion)",
        ],
    },
    "analysis": {
        "description": "Deep dive into a specific market dynamic",
        "flow": [
            "hook (bold claim or data point)",
            "background paragraph (set the scene)",
            "analysis paragraph 1 (the supply side)",
            "analysis paragraph 2 (the demand side or wild card)",
            "outlook paragraph (where this is headed)",
            "cta (ask for other perspectives)",
        ],
    },
    "story": {
        "description": "Tell a compelling story about the commodity world",
        "flow": [
            "hook (personal observation or vivid scene)",
            "story setup paragraph",
            "the turning point or revelation",
            "the broader lesson or insight",
            "cta (invite similar stories)",
        ],
    },
    "data_driven": {
        "description": "Lead with data and let numbers tell the story",
        "flow": [
            "hook (striking statistic)",
            "data context paragraph (what the numbers mean)",
            "comparison paragraph (historical or peer comparison)",
            "implication paragraph (so what?)",
            "cta (challenge the data or ask for more)",
        ],
    },
    "opinion": {
        "description": "Share a strong but reasoned opinion",
        "flow": [
            "hook (contrarian take or bold statement)",
            "the case paragraph (why you believe this)",
            "evidence paragraph (data or experience backing it)",
            "counterargument acknowledgment",
            "cta (invite debate)",
        ],
    },
    "current_event": {
        "description": "React to a breaking event with expert analysis",
        "flow": [
            "hook (reference the event directly)",
            "what happened paragraph (concise facts)",
            "why it matters paragraph (first-order effects)",
            "what to watch paragraph (second-order effects)",
            "cta (ask what others are watching)",
        ],
    },
}
