REJECTION_TYPES = [
    "skill_gap",               # lacks required technical skills
    "experience_insufficient", # not enough years or wrong type of experience
    "role_mismatch",           # wrong role type entirely (PM vs engineer)
    "culture_fit",             # soft skills or communication issues
    "overqualified",           # too senior or expensive for the role
    "salary_mismatch",         # rate expectations don't match
    "availability",            # timing or location doesn't work
    "client_rejected",         # client said no after interview
    "candidate_withdrew",      # candidate pulled out
    "better_candidate",        # another candidate was chosen
    "background_check",        # issues in verification
    "other",                   # doesn't fit categories above
]

REJECTION_STAGES = [
    "screening",            # initial resume review
    "technical_interview",  # technical assessment
    "client_interview",     # client-side interview
    "offer",                # offer stage (rejected offer or failed negotiation)
    "other",
]
