# Implementation Plan: Quadrant-Based Toast Placement Algorithm

## Overview

Replace the complex existing toast placement algorithm in the onboarding system with a simpler, more predictable quadrant-based placement system. The new algorithm determines toast placement based on which viewport quadrants the target element occupies, ensuring toasts are always visible and never overlap their targets.

## Types

### Quadrant Enumeration
```javascript
const QUADRANTS = {
  TOP_LEFT: 'top-left',
  TOP_RIGHT: 'top-right',
  BOTTOM_LEFT: 'bottom-left',
  BOTTOM_RIGHT: 'bottom-right'
};
```

### Position Object
```javascript
{
  top: number,    // Y coordinate in pixels
  left: number,   // X coordinate in pixels
  quadrants: Set  // Set of quadrant strings target occupies
}
```

## Files

### Files to Modify
- **myocyte/toxtempass/templates/toxtempass/base_extras/onboarding.html** (lines ~80-290)
  - Replace positioning logic within `showOnboardingToasts()` function
  - Remove complex fallback and nudging algorithms
  - Replace with simple quadrant-based calculation
  - Preserve: toast measurement, overlay management, Bootstrap integration, event handlers, smooth scrolling

### Files to Preserve (No Changes)
- All other files in the project remain unchanged
- The onboarding configuration structure remains the same
- The toast HTML structure and styling remain the same

## Functions

### Functions to Remove
These complex positioning functions will be completely removed:
- `makePositions()` - Creates candidate positions with multiple variants
- `fitsInsideViewport()` - Checks if position fits in viewport
- `overlapsTarget()` - Checks for target overlap
- `nudgeOffTarget()` - Attempts to adjust position to avoid overlap
- `clampToViewport()` - Clamps coordinates to viewport
- `rectDistance()` - Calculates distance between rectangles
- All fallback logic and position ranking code

### Functions to Add

**1. `determineQuadrants(rect, viewportWidth, viewportHeight)`**
- Purpose: Determine which quadrant(s) contain the target's bounding box
- Parameters:
  - `rect`: Target element's bounding rectangle
  - `viewportWidth`: Viewport width in pixels
  - `viewportHeight`: Viewport height in pixels
- Returns: Set of quadrant strings
- Logic:
  - Calculate viewport center: `centerX = viewportWidth / 2`, `centerY = viewportHeight / 2`
  - Check each corner of target rect against quadrant boundaries
  - Add quadrant to set if any part of target is in that quadrant

**2. `calculateQuadrantBasedPosition(quadrants, rect, toastWidth, toastHeight, viewportWidth, viewportHeight, margin)`**
- Purpose: Calculate toast position based on quadrant occupancy
- Parameters:
  - `quadrants`: Set of quadrants the target occupies
  - `rect`: Target bounding rectangle
  - `toastWidth`: Measured toast width
  - `toastHeight`: Measured toast height
  - `viewportWidth`: Viewport width
  - `viewportHeight`: Viewport height
  - `margin`: Margin from edges (default 10px)
- Returns: Position object `{top, left}`
- Logic: Implements B1-B9 placement rules (see Implementation Order section)

**3. `clampToViewport(position, toastWidth, toastHeight, viewportWidth, viewportHeight, margin)`**
- Purpose: Safety function to ensure toast stays within viewport bounds
- Parameters: Position and dimensions
- Returns: Adjusted position object
- Logic: Clamps top/left coordinates to `[margin, viewport - toast - margin]`

### Functions to Modify

**`showOnboardingToasts(messages, selectors)`**
- Keep existing structure for:
  - Container creation
  - Toast HTML generation
  - Bootstrap Toast initialization
  - Event handler setup
  - Overlay management
  - Smooth scrolling
- Replace only the positioning section (currently lines ~95-290) with new algorithm

## Classes

No new classes or class modifications required. The implementation uses plain JavaScript functions.

## Dependencies

No new dependencies required. The implementation uses:
- Existing Bootstrap 5.3.6 (already in project)
- Existing Bootstrap Toast component
- Standard DOM APIs (getBoundingClientRect, etc.)
- Existing viewport measurement approach (visualViewport API with fallback)

## Testing

### Manual Testing Approach
1. **Single Quadrant Tests (B1-B4)**
   - Create onboarding targets in each quadrant
   - Verify toast appears 10px away with correct anchor point
   - Test near edges to ensure proper clamping

2. **Horizontal Spanning Tests (B5-B6)**
   - Create wide targets spanning left-right quadrants
   - Top spanning: Verify centered horizontally, 10px below
   - Bottom spanning: Verify centered horizontally, 10px above

3. **Vertical Spanning Tests (B7-B8)**
   - Create tall targets spanning top-bottom quadrants
   - Left spanning: Verify centered vertically, 10px to right
   - Right spanning: Verify centered vertically, 10px to left

4. **Multi-Quadrant Test (B9)**
   - Create very large target spanning 3-4 quadrants
   - Verify toast centered in viewport

5. **Edge Cases**
   - Small viewport (mobile): Verify margin adjustment works
   - Very long toast content: Verify maxWidth caps work
   - Multiple toasts in sequence: Verify smooth transitions

### Test Pages
Test on these existing pages with onboarding configured:
- Start page (/)
- Overview page
- Create page (/add/)
- Answer page (/assay/*/answer/)

## Implementation Order

### Step 1: Add Helper Functions (New Code)
Add these three new functions after the `showOnboardingToasts` function declaration but before the positioning logic:

**1.1 Add `determineQuadrants()` function**
```javascript
function determineQuadrants(rect, viewportWidth, viewportHeight) {
  const centerX = viewportWidth / 2;
  const centerY = viewportHeight / 2;
  const quadrants = new Set();
  
  // Check which quadrants the target's bounding box intersects
  if (rect.left < centerX) {
    if (rect.top < centerY) quadrants.add('top-left');
    if (rect.bottom > centerY) quadrants.add('bottom-left');
  }
  if (rect.right > centerX) {
    if (rect.top < centerY) quadrants.add('top-right');
    if (rect.bottom > centerY) quadrants.add('bottom-right');
  }
  
  return quadrants;
}
```

**1.2 Add `calculateQuadrantBasedPosition()` function**
```javascript
function calculateQuadrantBasedPosition(quadrants, rect, toastWidth, toastHeight, viewportWidth, viewportHeight, margin) {
  const q = Array.from(quadrants);
  const qSet = quadrants;
  
  // Multi-quadrant spanning (B9: 3-4 quadrants)
  if (q.length >= 3) {
    return {
      top: (viewportHeight - toastHeight) / 2,
      left: (viewportWidth - toastWidth) / 2
    };
  }
  
  // Horizontal spanning
  const spansHorizontal = qSet.has('top-left') && qSet.has('top-right') || 
                          qSet.has('bottom-left') && qSet.has('bottom-right');
  const spansTop = qSet.has('top-left') && qSet.has('top-right');
  const spansBottom = qSet.has('bottom-left') && qSet.has('bottom-right');
  
  if (spansHorizontal) {
    const left = (viewportWidth - toastWidth) / 2;
    if (spansTop) {
      // B5: Top spanning - center horizontally, 10px below
      return { top: rect.bottom + margin, left: left };
    } else {
      // B6: Bottom spanning - center horizontally, 10px above
      return { top: rect.top - toastHeight - margin, left: left };
    }
  }
  
  // Vertical spanning
  const spansVertical = qSet.has('top-left') && qSet.has('bottom-left') ||
                        qSet.has('top-right') && qSet.has('bottom-right');
  const spansLeft = qSet.has('top-left') && qSet.has('bottom-left');
  const spansRight = qSet.has('top-right') && qSet.has('bottom-right');
  
  if (spansVertical) {
    const top = (viewportHeight - toastHeight) / 2;
    if (spansLeft) {
      // B7: Left spanning - center vertically, 10px to right
      return { top: top, left: rect.right + margin };
    } else {
      // B8: Right spanning - center vertically, 10px to left
      return { top: top, left: rect.left - toastWidth - margin };
    }
  }
  
  // Single quadrant (B1-B4)
  const quadrant = q[0];
  
  if (quadrant === 'top-left') {
    // B1: Top-left - 10px below, anchor top-left of toast to bottom-left of target
    return {
      top: rect.bottom + margin,
      left: rect.left
    };
  } else if (quadrant === 'top-right') {
    // B2: Top-right - 10px below, anchor top-right of toast to bottom-right of target
    return {
      top: rect.bottom + margin,
      left: rect.right - toastWidth
    };
  } else if (quadrant === 'bottom-left') {
    // B3: Bottom-left - 10px above, anchor bottom-left of toast to top-left of target
    return {
      top: rect.top - toastHeight - margin,
      left: rect.left
    };
  } else if (quadrant === 'bottom-right') {
    // B4: Bottom-right - 10px above, anchor bottom-right of toast to top-right of target
    return {
      top: rect.top - toastHeight - margin,
      left: rect.right - toastWidth
    };
  }
  
  // Fallback (should never reach here)
  return {
    top: (viewportHeight - toastHeight) / 2,
    left: (viewportWidth - toastWidth) / 2
  };
}
```

**1.3 Add `clampToViewport()` function (simplified version)**
```javascript
function clampToViewport(position, toastWidth, toastHeight, viewportWidth, viewportHeight, margin) {
  return {
    top: Math.max(margin, Math.min(position.top, viewportHeight - toastHeight - margin)),
    left: Math.max(margin, Math.min(position.left, viewportWidth - toastWidth - margin))
  };
}
```

### Step 2: Replace Positioning Logic
Replace the entire positioning section (lines ~95-290) with the new simplified algorithm:

**2.1 Remove old positioning code**
- Remove all existing positioning functions
- Remove the candidate positions logic
- Remove all fallback and nudging logic
- Keep the toast measurement section

**2.2 Add new positioning code**
After measuring the toast dimensions, replace with:
```javascript
// Get target bounding rect
const rect = target.getBoundingClientRect();

// Determine which quadrants the target occupies
const quadrants = determineQuadrants(rect, viewportWidth, viewportHeight);

// Calculate position based on quadrant rules
let position = calculateQuadrantBasedPosition(
  quadrants,
  rect,
  toastWidth,
  toastHeight,
  viewportWidth,
  viewportHeight,
  margin
);

// Safety clamp to ensure fully visible
position = clampToViewport(
  position,
  toastWidth,
  toastHeight,
  viewportWidth,
  viewportHeight,
  margin
);

// Apply the calculated position
toastEl.style.top = position.top + 'px';
toastEl.style.left = position.left + 'px';
toastEl.style.width = toastWidth + 'px';
toastEl.style.transform = 'translate(0,0)';
```

### Step 3: Preserve Existing Features
Ensure these remain unchanged:
- Overlay toggle functionality
- Toast container creation and management
- Toast HTML generation and content
- Bootstrap Toast initialization
- Event handlers (Next, Close buttons)
- Smooth scrolling (`scrollIntoView`)
- Step sequencing
- Z-index management
- Spared element highlighting

### Step 4: Test Implementation
- Test on multiple pages with onboarding configured
- Verify all 9 placement rules (B1-B9)
- Test edge cases (small viewport, near edges)
- Verify no regression in overlay, scrolling, events

## Summary

This refactoring simplifies the toast placement algorithm from ~200 lines of complex fallback logic to a straightforward ~100 lines of quadrant-based rules. The new algorithm is:
- **More predictable**: Placement follows clear quadrant rules
- **Easier to maintain**: Simple logic, no complex fallbacks
- **More reliable**: Fewer edge cases and failure modes
- **Better UX**: Consistent placement that users can anticipate

The implementation preserves all existing features (overlay, scrolling, Bootstrap integration) while only replacing the positioning calculation logic.
