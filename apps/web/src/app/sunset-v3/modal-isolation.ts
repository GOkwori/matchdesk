/** Temporarily keep a custom modal as the only interactive DOM subtree.
 *
 * aria-modal expresses semantics but does not itself make background controls
 * inert. Walk from the dialog to the document body, isolating sibling elements
 * at each level while preserving the modal's ancestor chain.
 *
 * Always restore the prior inert states on close and effect cleanup. This is
 * a browser-level guard, NOT proof of VoiceOver/NVDA acceptance.
 */
export function isolateModalBackground(modal: HTMLElement): () => void {
  const priorInertStates = new Map<HTMLElement, boolean>();

  for (
    let current: HTMLElement | null = modal;
    current?.parentElement && current !== document.body;
    current = current.parentElement
  ) {
    for (const sibling of current.parentElement.children) {
      if (sibling === current || !(sibling instanceof HTMLElement)) continue;
      priorInertStates.set(sibling, sibling.inert);
      sibling.inert = true;
    }
  }

  return () => {
    // Do not blindly remove inert; another control may have already set it.
    for (const [element, wasInert] of priorInertStates) {
      element.inert = wasInert;
    }
  };
}
