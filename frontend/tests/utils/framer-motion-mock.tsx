import React from 'react';

// Props that framer-motion adds that shouldn't be passed to DOM elements
const MOTION_PROPS = [
  'initial',
  'animate',
  'exit',
  'variants',
  'transition',
  'whileHover',
  'whileTap',
  'whileFocus',
  'whileDrag',
  'whileInView',
  'drag',
  'dragConstraints',
  'dragElastic',
  'dragMomentum',
  'dragTransition',
  'dragPropagation',
  'dragControls',
  'dragSnapToOrigin',
  'dragListener',
  'onDrag',
  'onDragStart',
  'onDragEnd',
  'onDirectionLock',
  'onDragTransitionEnd',
  'layout',
  'layoutId',
  'layoutDependency',
  'layoutScroll',
  'layoutRoot',
  'onLayoutAnimationStart',
  'onLayoutAnimationComplete',
  'onViewportEnter',
  'onViewportLeave',
  'viewport',
  'custom',
  'inherit',
  'onAnimationStart',
  'onAnimationComplete',
  'onUpdate',
  'onPan',
  'onPanStart',
  'onPanEnd',
  'onTap',
  'onTapStart',
  'onTapCancel',
  'onHoverStart',
  'onHoverEnd',
  'transformTemplate',
  'style', // Keep style but it's handled separately
];

// Filter out motion props from being passed to DOM
function filterMotionProps(props: Record<string, unknown>): Record<string, unknown> {
  const filtered: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(props)) {
    if (!MOTION_PROPS.includes(key)) {
      filtered[key] = value;
    }
  }

  // Always include style if it exists
  if (props.style) {
    filtered.style = props.style;
  }

  return filtered;
}

// Create a motion component mock for a given element type
function createMotionComponent(Element: string) {
  return React.forwardRef<HTMLElement, React.PropsWithChildren<Record<string, unknown>>>(
    ({ children, ...props }, ref) => {
      const filteredProps = filterMotionProps(props);
      return React.createElement(Element, { ...filteredProps, ref }, children);
    }
  );
}

// Export the mock object
export const motionMock = {
  motion: {
    div: createMotionComponent('div'),
    span: createMotionComponent('span'),
    button: createMotionComponent('button'),
    a: createMotionComponent('a'),
    ul: createMotionComponent('ul'),
    li: createMotionComponent('li'),
    nav: createMotionComponent('nav'),
    section: createMotionComponent('section'),
    article: createMotionComponent('article'),
    header: createMotionComponent('header'),
    footer: createMotionComponent('footer'),
    main: createMotionComponent('main'),
    aside: createMotionComponent('aside'),
    form: createMotionComponent('form'),
    input: createMotionComponent('input'),
    label: createMotionComponent('label'),
    p: createMotionComponent('p'),
    h1: createMotionComponent('h1'),
    h2: createMotionComponent('h2'),
    h3: createMotionComponent('h3'),
    h4: createMotionComponent('h4'),
    h5: createMotionComponent('h5'),
    h6: createMotionComponent('h6'),
    img: createMotionComponent('img'),
    svg: createMotionComponent('svg'),
    path: createMotionComponent('path'),
    circle: createMotionComponent('circle'),
    rect: createMotionComponent('rect'),
    line: createMotionComponent('line'),
    g: createMotionComponent('g'),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  useAnimation: () => ({
    start: () => Promise.resolve(),
    stop: () => {},
    set: () => {},
  }),
  useMotionValue: (initial: number) => ({
    get: () => initial,
    set: () => {},
    onChange: () => () => {},
  }),
  useTransform: (value: unknown, input: unknown, output: unknown) => ({
    get: () => (Array.isArray(output) ? output[0] : 0),
    set: () => {},
    onChange: () => () => {},
  }),
  useSpring: (value: unknown) => ({
    get: () => (typeof value === 'number' ? value : 0),
    set: () => {},
    onChange: () => () => {},
  }),
  useDragControls: () => ({
    start: () => {},
  }),
  useReducedMotion: () => false,
  useInView: () => true,
};

export default motionMock;
