import type {Metadata} from 'next';
import {Plus_Jakarta_Sans, JetBrains_Mono} from 'next/font/google';
import './globals.css';

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-sans',
  weight: ['400', '500', '600', '700'],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500', '600'],
});

export const metadata: Metadata = {
  title: 'Amaura Labs — North BlueStar Discovery Engine',
  description:
    'Method-agnostic algorithmic discovery engine, declarative candidate canonicalization, execution verification supervisor, and empirical research audit workbench.',
  openGraph: {
    title: 'Amaura Labs — North BlueStar Discovery Engine',
    description:
      'Method-agnostic algorithmic discovery engine, declarative candidate canonicalization, execution verification supervisor, and empirical research audit workbench.',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Amaura Labs — North BlueStar Discovery Engine',
    description:
      'Method-agnostic algorithmic discovery engine, declarative candidate canonicalization, execution verification supervisor, and empirical research audit workbench.',
  },
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${plusJakarta.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased bg-slate-950 text-slate-100" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
