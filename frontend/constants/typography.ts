// One type scale for the whole app. Pick from these, never invent sizes.
export const FS = {
  display: 28,  // large screen titles
  title: 20,    // hero names, big modal titles
  nav: 17,      // nav bar / sheet titles
  heading: 16,  // card + row titles, primary buttons
  body: 15,     // paragraphs, values, inputs
  secondary: 13, // subtitles, supporting text, chips
  caption: 12,  // meta, timestamps, eyebrow labels
  micro: 11,    // pills, badges
} as const;

// Uppercase section label used above every card/section.
export const EYEBROW = {
  fontSize: FS.caption,
  fontWeight: '700' as const,
  letterSpacing: 0.8,
  textTransform: 'uppercase' as const,
};
