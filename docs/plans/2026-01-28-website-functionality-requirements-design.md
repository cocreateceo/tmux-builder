# Website Functionality Requirements Design

**Date:** 2026-01-28
**Status:** Implemented

## Problem Statement

Websites created through tmux-builder were being deployed with non-functional UI elements:
- Buttons without onClick handlers
- Forms with only `e.preventDefault()` (no actual submission logic)
- Links with empty `href="#"`
- No cart system for e-commerce sites
- No localStorage persistence

## Solution

Updated the system prompt (`backend/system_prompt_generator.py`) to include mandatory functionality requirements that Claude must follow when creating any website.

## Architecture

```
User Request → tmux-builder → Claude CLI Session
                                    ↓
                          system_prompt.txt (includes requirements)
                                    ↓
                          Claude creates website with:
                          - Working onClick handlers
                          - Real form submission
                          - Cart system (e-commerce)
                          - localStorage persistence
                          - Toast notifications
                          - Success modals
```

## Key Requirements Added to System Prompt

### 1. Buttons Must Have onClick Handlers
```jsx
// Required pattern
<button onClick={() => addToCart(item)}>Add to Cart</button>
```

### 2. Forms Must Have Real Submit Logic
```jsx
const handleSubmit = (e) => {
  e.preventDefault();
  // Validate, save to localStorage, show success modal
};
<form onSubmit={handleSubmit}>...</form>
```

### 3. Links Must Have Real Destinations
```jsx
// Scroll links
<a href="#contact" onClick={(e) => {
  e.preventDefault();
  document.getElementById('contact').scrollIntoView({ behavior: 'smooth' });
}}>Contact</a>

// External links
<a href="https://facebook.com" target="_blank" rel="noopener noreferrer">Facebook</a>
```

### 4. E-Commerce Sites Must Include
- Cart state with useState
- Add/remove/update quantity functions
- Cart sidebar or modal
- Checkout modal with order summary
- Success modal with order confirmation
- localStorage persistence for cart

### 5. Form Sites Must Include
- Form state management
- Validation logic
- Success feedback (modal or message)
- localStorage for form submissions

## Checklists in System Prompt

### E-Commerce Checklist
- [ ] "Add to Cart" buttons add items to cart state
- [ ] Cart shows item count badge
- [ ] Cart modal/sidebar shows all items
- [ ] Can increase/decrease quantity
- [ ] Can remove items from cart
- [ ] Checkout button shows order summary
- [ ] Order confirmation modal appears
- [ ] localStorage persists cart between refreshes

### Form/Reservation Checklist
- [ ] Form validates required fields
- [ ] Submit button triggers handleSubmit
- [ ] Success modal/message appears after submit
- [ ] Form data saved to localStorage
- [ ] Error messages show for invalid input

## Code Templates Provided

The system prompt includes complete code templates for:
1. Cart system with localStorage
2. Form submission with localStorage
3. Toast notifications
4. Modal components

## Files Modified

- `backend/system_prompt_generator.py` - Added ~150 lines of functionality requirements

## Testing

Verified by fixing existing websites:
- Restaurant website - Full cart + reservation form
- Pet Shop website - Full cart + contact form
- Mobile Shop website - Full cart + contact form

## Future Considerations

1. Could add more website type templates (blog, portfolio, SaaS landing page)
2. Could add automated testing to verify functionality before deployment
3. Could create reusable component library for common patterns
