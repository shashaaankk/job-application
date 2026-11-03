\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{bmsnkresume}[2024/12/07 Resume Class]
\LoadClass[a4paper]{article}
\RequirePackage[fontsize=10pt]{fontsize}
% Body leading. LaTeX's default is 1.2, which is tight for Calibri's large
% x-height. 1.09 x 1.2 = 1.31. Raise or lower this one number to retune.
\linespread{1.06}

% Packages
% Calibri via fontspec. Requires XeLaTeX or LuaLaTeX; pdflatex cannot load
% TrueType/OpenType faces directly. inputenc and fontenc are deliberately
% absent because fontspec handles input and font encoding under both engines.
\RequirePackage{fontspec}
\setmainfont{Calibri}
\setsansfont{Calibri}
\renewcommand{\familydefault}{\sfdefault}

% Emphasis is carried by SIZE, not weight (user directive 2026-08-27).
% \cvemphsize sets the following text 1pt larger than whatever size is
% current, so it scales correctly inside \small or an explicit \fontsize.
% Bold is banned. Use \cvemphsize instead of any weight change.
\newcommand{\cvemphsize}{\fontsize{\dimexpr\f@size pt+1pt\relax}{\dimexpr\f@baselineskip+1pt\relax}\selectfont}
\RequirePackage[top=0.66in, bottom=0.6in, left=0.6in, right=0.6in]{geometry}
\RequirePackage{xcolor}
\RequirePackage{tikz}
\RequirePackage{graphicx}
\RequirePackage{ifthen}
\RequirePackage{parskip}
\RequirePackage{hyperref}
% Link style default, user directive 2026-08-17: links render blue.
% Clickable text is lowercase and \footnotesize at the call site.
\hypersetup{colorlinks=true, urlcolor=blue, linkcolor=blue, citecolor=blue}

% Colors
\definecolor{primary}{RGB}{41, 98, 155}
\definecolor{darktext}{RGB}{50, 50, 50}
\definecolor{lighttext}{RGB}{120, 120, 120}

% Header background tint
\colorlet{headerbg}{primary!6}
\newcommand{\setheaderbg}[1]{\colorlet{headerbg}{#1}}

\pagestyle{empty}

% Store info
\newcommand{\@fullname}{}
\newcommand{\@professionaldescription}{}
\newcommand{\@contact}{}
\newcommand{\@socials}{}
\newcommand{\@photopath}{}

\newcommand{\name}[1]{\renewcommand{\@fullname}{#1}}
\newcommand{\professional}[1]{\renewcommand{\@professionaldescription}{#1}}
\newcommand{\contact}[1]{\renewcommand{\@contact}{#1}}
\newcommand{\socials}[1]{\renewcommand{\@socials}{#1}}
\newcommand{\photo}[1]{\renewcommand{\@photopath}{#1}}

% Photo switch. User directive 2026-08-17: India-market CVs carry no photo and no
% placeholder frame. Call \nophoto in the preamble to drop the image, its circle
% and the reserved column; the text block then spans the full header width.
\newif\ifbmsnk@showphoto
\bmsnk@showphototrue
\newcommand{\nophoto}{\bmsnk@showphotofalse}

% Center-justified header text, per-file experiment switch (2026-08-27).
\newif\ifbmsnk@centerheader
\bmsnk@centerheaderfalse
\newcommand{\centerheader}{\bmsnk@centerheadertrue}

% ============================================================================
% HEADER
% ============================================================================
\newcommand{\makeheader}{%
    \noindent
    \colorbox{headerbg}{%
      \parbox{\dimexpr\textwidth-2\fboxsep\relax}{%
        \begin{minipage}[c]{\ifbmsnk@showphoto 0.78\else 1.0\fi\textwidth}
            \ifbmsnk@centerheader\centering\fi
            % Line 1: Name
            {\fontsize{16}{19}\selectfont\cvemphsize\color{primary}\@fullname}
            
            \vspace{0.15em}
            
            % Line 2: Professional description
            {\color{darktext}\@professionaldescription}
            
            \vspace{0.7em}
            
            % Line 3: Contact line
            {\small\color{darktext}\@contact}
            
            \vspace{0.1em}
            
            % Line 4: Social links
            {\small\color{darktext}\@socials}
        \end{minipage}%
        \ifbmsnk@showphoto
        \hfill%
        \begin{minipage}[c]{0.18\textwidth}
            \raggedleft
            \ifthenelse{\equal{\@photopath}{}}{%
                \begin{tikzpicture}
                    \draw[color=lighttext, line width=0.8pt] (0,0) circle (1.2cm);
                    \node[color=lighttext, font=\tiny] at (0,0) {Photo};
                \end{tikzpicture}%
            }{%
                \begin{tikzpicture}
                    \clip (0,0) circle (1.1cm);
                    \node at (0,-0.95) {\includegraphics[width=3.5cm]{potrait00.png}};
                    \draw[thin, black] (0,0) circle (1.1cm);
                \end{tikzpicture}
            }
        \end{minipage}%
        \fi
      }%
    }%
    \vspace{0.5em}%
}

% ============================================================================
% SECTION TITLE
% ============================================================================
\newcommand{\sectiontitle}[1]{%
  \par\vspace{1.0em}%
  {%
    \setlength{\parskip}{0pt}%
    \setlength{\parindent}{0pt}%
    \noindent{\cvemphsize \color{darktext}\MakeUppercase{#1}}\par
    \vspace{-0.85em}%
    \noindent\color{lighttext}\rule{\linewidth}{0.3pt}\par
  }%
  \vspace{-1.05em}%
}

% ============================================================================
% EXPERIENCE ENTRY
% ============================================================================
\RequirePackage{enumitem}
% nosep removed: it collapsed the gap between consecutive bullets to zero.
% itemsep is the space between bullets, topsep the space above the list.
\setlist[itemize]{leftmargin=1.5em, topsep=0.15em, itemsep=0.20em, parsep=0pt}

\newcommand{\experience}[4]{%
    % #1 = Organization
    % #2 = Location
    % #3 = Title
    % #4 = Timeline

    \noindent%
    \begin{minipage}[t]{0.62\textwidth}%
        {\cvemphsize\color{darktext}#3}%
    \end{minipage}%
    \hfill%
    \begin{minipage}[t]{0.36\textwidth}%
        \raggedleft{\color{darktext}#4}%
    \end{minipage}%
    \\[0.05em]
    \noindent%
    \begin{minipage}[t]{0.62\textwidth}%
        {\color{darktext}#1}%
    \end{minipage}%
    \hfill%
    \begin{minipage}[t]{0.36\textwidth}%
        \raggedleft{\color{darktext}#2}%
    \end{minipage}%
    \par\vspace{0.1em}%
}

% ============================================================================
% EDUCATION ENTRY
% ============================================================================
\newcommand{\educationentry}[5]{%
    % #1 = Degree
    % #2 = Institution
    % #3 = Timeline
    % #4 = Score
    % #5 = Relevant coursework

    \noindent%
    \begin{minipage}[t]{0.62\textwidth}%
        {\cvemphsize\color{darktext}#1}%
    \end{minipage}%
    \hfill%
    \begin{minipage}[t]{0.36\textwidth}%
        \raggedleft{\color{darktext}#3}%
    \end{minipage}%
    \\[0.05em]
    \noindent%
    \begin{minipage}[t]{0.62\textwidth}%
        {\color{darktext}#2}%
    \end{minipage}%
    \hfill%
    \begin{minipage}[t]{0.36\textwidth}%
        \raggedleft{\color{darktext}#4}%
    \end{minipage}%
    \par\vspace{0.1em}%
    \ifthenelse{\equal{#5}{}}{}{%
        {\small\color{darktext}{\cvemphsize Relevant Coursework:} #5}%
        \par%
    }%
    \vspace{0.35em}%
}

% ============================================================================
% SKILLS
% ============================================================================
\newcommand{\technicalskills}[1]{%
  {\cvemphsize\color{darktext}Technical Skills}\par
  \vspace{-0.5em}%
  {\color{darktext}#1}\par\vspace{0.1em}%
}

\newcommand{\languages}[1]{%
  {\cvemphsize\color{darktext}Languages}\par
  \vspace{-0.5em}%
  {\color{darktext}#1}\par\vspace{0.1em}%
}

% ============================================================================
% ACADEMICS ENTRY
% ============================================================================
\newcommand{\academicsentry}[4]{%
    % #1 = Heading
    % #2 = Timeline
    % #3 = Title
    % #4 = Institute

    \noindent%
    \begin{minipage}[t]{0.76\textwidth}%
        {\cvemphsize\color{darktext}#1}%
    \end{minipage}%
    \hfill%
    \begin{minipage}[t]{0.22\textwidth}%
        \raggedleft{\color{darktext}#2}%
    \end{minipage}%
    \\[0.02em]
    \ifthenelse{\equal{#3}{}}{}{%
        \noindent%
        \begin{minipage}[t]{\textwidth}%
            {\cvemphsize\color{darktext}#3}%
        \end{minipage}%
        \\[0.02em]
    }%
    \noindent%
    \begin{minipage}[t]{\textwidth}%
        {\color{darktext}#4}%
    \end{minipage}%
    \par\vspace{0.15em}%
}

\newcommand{\publicationline}[1]{#1\par}

% ============================================================================
% ACTIVITIES AND ACHIEVEMENTS
% ============================================================================
\newenvironment{achievements}{%
  \begin{itemize}%
}{%
  \end{itemize}%
  \vspace{0.15em}%
}

% ============================================================================
% ADDITIONAL COURSE ENTRY
% ============================================================================
\newcommand{\courseentry}[4]{%
    % #1 = Title
    % #2 = Provider
    % #3 = Date
    % #4 = Description

    \noindent%
    \begin{minipage}[t]{0.62\textwidth}%
        {\cvemphsize\color{darktext}#1}%
    \end{minipage}%
    \hfill%
    \begin{minipage}[t]{0.36\textwidth}%
        \raggedleft{\color{darktext}#3}%
    \end{minipage}%
    \\[0.05em]
    \noindent%
    \begin{minipage}[t]{\textwidth}%
        {\color{darktext}#2}%
    \end{minipage}%
    \ifthenelse{\equal{#4}{}}{}{%
        \\[0.05em]
        \noindent%
        \begin{minipage}[t]{\textwidth}%
            {\small\color{darktext}#4}%
        \end{minipage}%
    }%
    \par\vspace{0.05em}%
}
% ============================================================================
% PROJECT ENTRY
% ============================================================================
\newcommand{\projectentry}[2]{%
    % #1 = Title
    % #2 = Tech Stack

    \noindent%
    {\cvemphsize\color{darktext}#1}\\[-0.1em]
    {\color{darktext}{\cvemphsize Tech Stack:} #2}%
    % \par\vspace{0.01em}%
}
\endinput