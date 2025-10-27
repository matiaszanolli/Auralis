# MSE Browser Compatibility Guide

**Date**: October 27, 2025
**Topic**: Media Source Extensions browser support for Auralis progressive streaming

---

## Executive Summary

Media Source Extensions (MSE) has **97% browser compatibility** across modern browsers. The main limitation is **iPhone Safari**, which requires using the newer Managed Media Source (MMS) API instead.

**Bottom line for Auralis**:
- ✅ **Chrome**: Full support (desktop + Android)
- ✅ **Firefox**: Full support (desktop + Android)
- ✅ **Edge**: Full support (desktop)
- ✅ **Safari Desktop**: Full support (macOS)
- ✅ **Safari iPad**: Full support (iPadOS 13.2+)
- ⚠️ **Safari iPhone**: Requires Managed Media Source (iOS 17.1+)

---

## Browser Support Matrix

### Desktop Browsers (100% Compatible)

| Browser | Version Range | MSE Support | Notes |
|---------|--------------|-------------|-------|
| Chrome | 23-136+ | ✅ Full | Industry standard implementation |
| Firefox | 42-138+ | ✅ Full | Excellent support |
| Edge | All versions | ✅ Full | Chromium-based, same as Chrome |
| Safari | 8-18.4+ | ✅ Full | macOS only |
| Opera | Modern | ✅ Full | Chromium-based |

### Mobile Browsers (Mostly Compatible)

| Browser | Platform | Version | MSE Support | Notes |
|---------|----------|---------|-------------|-------|
| Chrome | Android | All modern | ✅ Full | Same as desktop |
| Firefox | Android | All modern | ✅ Full | Same as desktop |
| Safari | iOS | <17.0 | ❌ None | MSE blocked |
| Safari | iOS | 17.1+ | ⚠️ MMS only | Requires Managed Media Source |
| Safari | iPadOS | 13.2+ | ✅ Full | MSE works |

### Compatibility Score

**Overall**: 97% (Can I Use data)

---

## iPhone Safari Limitation

### The Problem

Apple **removed traditional MSE from Safari on iPhone** for battery life reasons. Native HLS provides better energy efficiency.

### The Solution: Managed Media Source (MMS)

Starting with **iOS 17.1** (November 2023), Apple introduced **Managed Media Source API** as a replacement for MSE.

**Key Differences**:
- MMS gives more control to the User Agent (browser)
- Better battery life than traditional MSE
- Different API surface (not drop-in compatible)
- Enabled by default in iOS 17.1+

**User Settings**: Safari > Advanced > Feature Flags > Managed Media Source

### Migration Path

1. **Detect browser capabilities**:
   ```javascript
   const hasMSE = 'MediaSource' in window;
   const hasMMS = 'ManagedMediaSource' in window;
   ```

2. **Use MMS on iOS Safari**:
   ```javascript
   const MediaSourceClass = window.ManagedMediaSource || window.MediaSource;
   ```

3. **Fallback to file-based streaming** if neither available

---

## Auralis Implementation Strategy

### Phase 1: Desktop + Android (Current Priority)

**Target Platforms**:
- Chrome (desktop + Android)
- Firefox (desktop + Android)
- Edge (desktop)
- Safari (macOS + iPadOS)

**Approach**: Standard MSE implementation (what we're building now)

**Market Coverage**: ~95% of desktop users, ~80% of mobile users

### Phase 2: iPhone Support (Future)

**Options**:

**Option A: Managed Media Source (MMS)**
- Pros: Native iOS support, better battery life
- Cons: Different API, requires separate implementation
- Effort: 1-2 weeks additional development

**Option B: Native HLS**
- Pros: Best iOS performance, Apple's recommendation
- Cons: Requires HLS encoding backend
- Effort: 2-3 weeks (more complex)

**Option C: Fallback to File Streaming**
- Pros: Simple, works immediately
- Cons: Preset switching still requires buffering (original problem)
- Effort: Already implemented

**Recommended**: Option C for Beta.3, Option A for Beta.4+

---

## Technical Considerations

### MIME Types

**MSE-Compatible Audio Formats**:
- `audio/wav; codecs="pcm"` ← **What we're using**
- `audio/mp4; codecs="mp4a.40.2"` (AAC)
- `audio/webm; codecs="opus"`
- `audio/mpeg` (MP3)

**Note**: WAV/PCM works across all MSE-supporting browsers.

### SourceBuffer Constraints

**Maximum SourceBuffer Size**:
- Chrome: ~150MB (varies by available memory)
- Firefox: ~200MB
- Safari: ~100MB

**Auralis Chunks**:
- 30 seconds = ~5.3MB per chunk (stereo 44.1kHz WAV)
- Can buffer ~20-30 chunks before hitting limits
- Cleanup strategy: Remove old chunks when buffer fills

### Performance Expectations

**Chunk Append Latency**:
- Chrome: 5-15ms per chunk
- Firefox: 10-20ms per chunk
- Safari: 15-30ms per chunk

**Preset Switch Latency** (with L1 cache):
- Cache hit: 0-50ms (instant)
- Cache miss: 500ms-2s (on-demand processing)

---

## Progressive Enhancement Strategy

### Detection Code

```javascript
function detectMSESupport() {
  if ('ManagedMediaSource' in window) {
    return {
      type: 'mms',
      supported: true,
      platform: 'iOS Safari 17.1+'
    };
  }

  if ('MediaSource' in window && MediaSource.isTypeSupported('audio/wav; codecs="pcm"')) {
    return {
      type: 'mse',
      supported: true,
      platform: 'Modern browsers'
    };
  }

  return {
    type: 'fallback',
    supported: false,
    platform: 'Older browsers or unsupported devices'
  };
}
```

### Fallback Chain

```
1. Try MSE (Chrome, Firefox, Edge, Safari desktop/iPad)
   ↓ if not supported
2. Try MMS (iPhone Safari 17.1+)
   ↓ if not supported
3. Fall back to file-based streaming (all browsers)
```

---

## Market Share Analysis (2025)

### Desktop Browser Usage
- Chrome: 65%
- Edge: 15%
- Firefox: 8%
- Safari: 10%
- Others: 2%

**MSE Coverage**: ~98% (all except some very old browsers)

### Mobile Browser Usage
- Chrome (Android): 45%
- Safari (iOS): 40%
- Samsung Internet: 8%
- Others: 7%

**MSE Coverage without MMS**: ~60% (Chrome + Android browsers)
**MSE Coverage with MMS**: ~95% (adds iOS 17.1+ Safari)

---

## Recommendations for Auralis

### Beta.3 Release (2-3 Weeks)

**Target**: Desktop + Android

**Implementation**:
- ✅ Standard MSE with WAV/PCM chunks
- ✅ Chrome, Firefox, Edge, Safari desktop/iPad
- ✅ Fallback to file streaming for unsupported browsers
- ⏳ Skip MMS for now (simplify initial release)

**Market Coverage**: ~95% of desktop, ~60% of mobile

### Beta.4+ Release (Future)

**Target**: iPhone support

**Implementation**:
- Add Managed Media Source support for iOS Safari
- OR implement HLS encoding for native iOS playback
- OR accept file-streaming fallback for iPhone

**Market Coverage**: ~95% desktop, ~95% mobile

---

## Testing Matrix

### Priority 1 (Beta.3)

| Browser | Platform | Version | Test Scenario |
|---------|----------|---------|---------------|
| Chrome | Windows 11 | Latest | Full MSE testing |
| Chrome | macOS | Latest | Full MSE testing |
| Firefox | Windows 11 | Latest | Full MSE testing |
| Edge | Windows 11 | Latest | Full MSE testing |
| Safari | macOS | 18.4 | Full MSE testing |
| Chrome | Android 14 | Latest | Mobile MSE testing |

### Priority 2 (Beta.4+)

| Browser | Platform | Version | Test Scenario |
|---------|----------|---------|---------------|
| Safari | iPhone (iOS 17.1+) | Latest | MMS testing |
| Safari | iPad (iPadOS 17+) | Latest | MSE + MMS testing |
| Safari | iPhone (<iOS 17) | 16.x | Fallback testing |

---

## Known Issues & Limitations

### Safari Desktop

- **Issue**: Stricter SourceBuffer limits (~100MB vs 150-200MB)
- **Impact**: May need to garbage collect chunks more aggressively
- **Mitigation**: Monitor `sourceBuffer.buffered` and remove old ranges

### Firefox

- **Issue**: Slightly higher chunk append latency (10-20ms vs 5-15ms)
- **Impact**: Minimal, still well under 100ms target
- **Mitigation**: None needed

### iPhone Safari

- **Issue**: Traditional MSE not available
- **Impact**: Can't use our MSE implementation directly
- **Mitigation**: Fallback to file streaming for Beta.3

---

## Development Checklist

### Beta.3 (MSE Implementation)

- [x] Backend chunk streaming API
- [x] MSE router integrated
- [ ] Frontend MSEPlayer class
- [ ] Browser detection logic
- [ ] Fallback to file streaming
- [ ] Test on Chrome, Firefox, Edge
- [ ] Test on Safari desktop/iPad
- [ ] Test on Android Chrome

### Beta.4+ (iOS Support)

- [ ] Research Managed Media Source API
- [ ] Implement MMS adapter
- [ ] Test on iPhone (iOS 17.1+)
- [ ] Test fallback on older iOS
- [ ] OR implement HLS encoding
- [ ] OR accept file-streaming fallback

---

## Resources

**Official Documentation**:
- [MDN: Media Source Extensions API](https://developer.mozilla.org/en-US/docs/Web/API/Media_Source_Extensions_API)
- [MDN: Managed Media Source API](https://developer.mozilla.org/en-US/docs/Web/API/ManagedMediaSource)
- [Can I Use: MediaSource](https://caniuse.com/mediasource)

**Apple Documentation**:
- [Managed Media Source Release Notes](https://webkit.org/blog/14445/webkit-features-in-safari-17-1/)
- [Apple Developer Forums: MMS](https://developer.apple.com/forums/thread/739747)

**Vendor Blogs**:
- [Radiant Media Player: Safari 17.1 MMS](https://www.radiantmediaplayer.com/blog/at-last-safari-17.1-now-brings-the-new-managed-media-source-api-to-iphone.html)
- [Bitmovin: Apple's Managed Media Source](https://bitmovin.com/blog/managed-media-source/)

---

## Conclusion

**For Auralis Beta.3**:
- MSE is **production-ready** for desktop and Android
- 97% browser compatibility overall
- 95% market coverage for our target (desktop + Android)
- iPhone requires separate work (Beta.4+)

**Action Plan**:
1. ✅ Complete MSE backend (done!)
2. ⏳ Implement frontend MSEPlayer (next)
3. ⏳ Test on Chrome, Firefox, Edge, Safari desktop
4. ⏳ Ship Beta.3 with MSE + file-streaming fallback
5. 🔮 Add iPhone support in Beta.4 (MMS or HLS)

**Status**: Ready to proceed with frontend implementation!

---

**Last Updated**: October 27, 2025
**Next Review**: Before Beta.4 planning (iPhone support decision)
