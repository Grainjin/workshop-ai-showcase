import type { DiagramContent } from '../content/types';

export default function DiagramFigure({ content }: { content: DiagramContent }) {
  return (
    <figure className="diagram-figure">
      <img src={content.src} alt={content.title} loading="lazy" />
      <figcaption>{content.description}</figcaption>
    </figure>
  );
}
