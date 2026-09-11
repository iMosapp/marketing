import React from 'react';
import { View, Text, Platform } from 'react-native';

// Lightweight markdown for the internal docs: headings, bullets, numbered lists, tables, code fences, bold + inline code.
export function renderInlineMarkdown(text: string, colors: any): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <Text key={idx} style={{ fontWeight: '700', color: colors.text }}>{part.slice(2, -2)}</Text>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <Text key={idx} style={{ fontFamily: Platform.OS === 'web' ? 'monospace' : 'Courier', backgroundColor: colors.card, color: '#FF9500', fontSize: 14, paddingHorizontal: 4, borderRadius: 3 }}>
          {part.slice(1, -1)}
        </Text>
      );
    }
    return <Text key={idx}>{part.replace(/_([^_]+)_/g, '$1')}</Text>;
  });
}

const splitRow = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());

export function MarkdownRenderer({ content, colors }: { content: string; colors: any }) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  const mono = Platform.OS === 'web' ? 'monospace' : 'Courier';
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed === '') { elements.push(<View key={i} style={{ height: 8 }} />); i++; continue; }

    if (trimmed.startsWith('```')) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) { code.push(lines[i]); i++; }
      i++;
      elements.push(
        <View key={`code-${i}`} style={{ backgroundColor: colors.card, borderRadius: 10, padding: 12, marginVertical: 8 }}>
          <Text style={{ fontFamily: mono, fontSize: 12.5, color: colors.text, lineHeight: 18 }}>{code.join('\n')}</Text>
        </View>
      );
      continue;
    }

    if (trimmed.startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        const cells = splitRow(lines[i]);
        if (!cells.every(c => /^:?-{2,}:?$/.test(c))) rows.push(cells);
        i++;
      }
      const [head, ...body] = rows;
      elements.push(
        <View key={`table-${i}`} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, overflow: 'hidden', marginVertical: 8 }}>
          {head && head.some(Boolean) && (
            <View style={{ flexDirection: 'row', backgroundColor: colors.card, paddingVertical: 8, paddingHorizontal: 10, gap: 10 }}>
              {head.map((c, ci) => <Text key={ci} style={{ flex: ci === 0 ? 1.1 : 1.6, fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>{c.toUpperCase()}</Text>)}
            </View>
          )}
          {body.map((r, ri) => (
            <View key={ri} style={{ flexDirection: 'row', paddingVertical: 9, paddingHorizontal: 10, gap: 10, borderTopWidth: 1, borderTopColor: colors.border }}>
              {r.map((c, ci) => <Text key={ci} style={{ flex: ci === 0 ? 1.1 : 1.6, fontSize: 14, color: ci === 0 ? colors.text : colors.textSecondary, lineHeight: 20 }}>{renderInlineMarkdown(c, colors)}</Text>)}
            </View>
          ))}
        </View>
      );
      continue;
    }

    if (trimmed.startsWith('# ') && !trimmed.startsWith('## ')) {
      elements.push(<Text key={i} style={{ fontSize: 24, fontWeight: '800', color: colors.text, marginTop: 24, marginBottom: 8, letterSpacing: -0.3 }}>{trimmed.replace(/^# /, '')}</Text>);
      i++; continue;
    }
    if (trimmed.startsWith('## ')) {
      elements.push(<Text key={i} style={{ fontSize: 19, fontWeight: '700', color: colors.text, marginTop: 20, marginBottom: 6 }}>{trimmed.replace(/^## /, '')}</Text>);
      i++; continue;
    }
    if (trimmed.startsWith('### ')) {
      elements.push(<Text key={i} style={{ fontSize: 17, fontWeight: '700', color: '#AF52DE', marginTop: 16, marginBottom: 4 }}>{trimmed.replace(/^### /, '')}</Text>);
      i++; continue;
    }
    if (trimmed === '---') {
      elements.push(<View key={i} style={{ height: 1, backgroundColor: colors.card, marginVertical: 16 }} />);
      i++; continue;
    }
    if (trimmed.startsWith('> ')) {
      elements.push(
        <View key={i} style={{ borderLeftWidth: 3, borderLeftColor: '#C9A962', backgroundColor: '#C9A96214', paddingVertical: 10, paddingHorizontal: 12, borderRadius: 8, marginVertical: 6 }}>
          <Text style={{ fontSize: 16, color: colors.text, lineHeight: 23 }}>{renderInlineMarkdown(trimmed.replace(/^> /, ''), colors)}</Text>
        </View>
      );
      i++; continue;
    }
    if (/^\d+\.\s/.test(trimmed)) {
      const [, num, rest] = trimmed.match(/^(\d+)\.\s(.*)$/) || [];
      elements.push(
        <View key={i} style={{ flexDirection: 'row', paddingLeft: 8, marginBottom: 4 }}>
          <Text style={{ fontSize: 16, color: '#AF52DE', marginRight: 8, fontWeight: '700', width: 22 }}>{num}.</Text>
          <Text style={{ fontSize: 16, color: colors.text, opacity: 0.85, lineHeight: 22, flex: 1 }}>{renderInlineMarkdown(rest || '', colors)}</Text>
        </View>
      );
      i++; continue;
    }
    if (trimmed.startsWith('- ') && !line.startsWith('  ')) {
      elements.push(
        <View key={i} style={{ flexDirection: 'row', paddingLeft: 8, marginBottom: 4 }}>
          <Text style={{ fontSize: 16, color: '#AF52DE', marginRight: 8, marginTop: 1 }}>*</Text>
          <Text style={{ fontSize: 16, color: colors.text, opacity: 0.85, lineHeight: 22, flex: 1 }}>{renderInlineMarkdown(trimmed.replace(/^- /, ''), colors)}</Text>
        </View>
      );
      i++; continue;
    }
    if (trimmed.startsWith('- ')) {
      elements.push(
        <View key={i} style={{ flexDirection: 'row', paddingLeft: 24, marginBottom: 3 }}>
          <Text style={{ fontSize: 14, color: colors.textSecondary, marginRight: 8 }}>-</Text>
          <Text style={{ fontSize: 15, color: colors.textSecondary, lineHeight: 20, flex: 1 }}>{renderInlineMarkdown(trimmed.replace(/^- /, ''), colors)}</Text>
        </View>
      );
      i++; continue;
    }

    elements.push(<Text key={i} style={{ fontSize: 16, color: colors.text, opacity: 0.85, lineHeight: 22, marginBottom: 4 }}>{renderInlineMarkdown(trimmed, colors)}</Text>);
    i++;
  }

  return <>{elements}</>;
}
