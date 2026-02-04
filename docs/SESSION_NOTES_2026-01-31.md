# Session Notes - January 31, 2026

## Summary

Focused on fixing website layout generation issues in the system prompt. After multiple iterations trying complex solutions, reverted to basic working version with layout priority rules.

## What Was Accomplished

### System Prompt Generator Updates

1. **Layout Issues Identified**
   - Generated websites had content pushed to left with empty space on right
   - Caused by conflicting directives: "next-gen design" vs "layout correctness"
   - Floating elements, glassmorphism, and absolute positioning broke layouts

2. **Solution Applied (Basic Level)**
   - Added "Visual Authority Rule" - layout correctness is highest priority
   - Added "Hard Layout Invariants" - content must be centered, no asymmetric space
   - Added "Forbidden Patterns" - patterns that cause layout breaks
   - Changed design guidelines to "OPTIONAL ENHANCEMENTS"
   - Simplified hierarchy: Layout > Sections > Effects

3. **Attempted Simplifications (Reverted)**
   - Tried ultra-simple 243-line version with strict single-column template
   - Tried adding full functionality patterns (cart, modal, toast)
   - Both caused issues - Claude either ignored constraints or over-complicated
   - Reverted to original 970-line version with layout priority rules added

### Client Onboarding Simplification

1. **Removed Country Code Selector**
   - Simplified phone input to single field
   - Removed complex dropdown with 20+ country codes
   - Simplified phone validation

2. **Added Field Trimming**
   - All form fields trimmed before submit
   - Email converted to lowercase

## Files Modified

| File | Changes |
|------|---------|
| `backend/system_prompt_generator.py` | Added Visual Authority Rule, Hard Layout Invariants, Forbidden Patterns |
| `frontend/src/client/ClientOnboarding.jsx` | Removed country code selector, simplified phone input |

## Commits

```
b628a6c feat: Basic level website generation and simplified onboarding
```

## Deployment Status

| Component | Location | Status |
|-----------|----------|--------|
| Backend Code | EC2 ~/tmux-builder/backend | ✅ Deployed |
| Frontend Code | EC2 ~/tmux-builder/frontend | Needs deploy |
| system_prompt_generator.py | EC2 | ✅ Deployed (970 lines) |

## Key Learnings

### What Didn't Work
1. **Ultra-simple templates** - Claude still made complex layouts
2. **Strict "DO NOT" rules** - Claude ignored them
3. **Adding functionality patterns** - Made layouts worse
4. **Two-column layouts** - Consistently broke centering

### What Works
1. **Original prompt with layout priority** - Basic level with Visual Authority Rule
2. **Simple color scheme** - `bg-slate-900`, `bg-slate-800`
3. **Centered content pattern** - `max-w-4xl mx-auto px-4`
4. **Single column layouts** - More reliable than grids

## Client UI Files Reference

```
frontend/src/client/
├── ClientApp.jsx              # Main client dashboard
├── ClientOnboarding.jsx       # Onboarding form (/client_input)
├── index.js                   # Exports
├── components/
│   ├── ActivityPanel.jsx      # Real-time activity log
│   ├── ChatPanel.jsx          # Chat interface
│   ├── NewProjectModal.jsx    # Create project modal
│   └── ProjectSidebar.jsx     # Project list sidebar
├── context/
│   └── ThemeContext.jsx       # Dark/light theme
├── hooks/
│   ├── useClientSession.js    # Session state management
│   └── useTheme.js            # Theme hook
└── services/
    └── clientApi.js           # API service
```

## Routes

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | SplitChatView | Admin dashboard |
| `/client_input` | ClientOnboarding | New client form |
| `/onboard` | ClientOnboarding | Alias for client_input |
| `/client?guid=xxx` | ClientApp | Client project dashboard |
| `/client?email=xxx` | ClientApp | Client dashboard by email |

## Pending / Next Steps

1. [ ] Deploy frontend changes to EC2
2. [ ] Test new website generation with basic prompt
3. [ ] Consider adding functionality patterns incrementally after layout is stable
4. [ ] Clean up temp files (nexusdigital_fixed_*.jsx, images)

## Notes for Next Session

- The system prompt is 970 lines - this is intentional, it's the working version
- Layout priority is: centered > complete > fancy effects
- Don't try to simplify the prompt too much - Claude needs detailed instructions
- Test website generation on EC2, not locally
- AWS profile for deployment: `cocreate`
