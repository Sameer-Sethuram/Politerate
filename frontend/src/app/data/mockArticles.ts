export type BiasRating = "left" | "lean-left" | "center" | "lean-right" | "right";

export interface Article {
  id: string;
  title: string;
  source: string;
  bias: BiasRating;
  trustScore: number; // 0-100
  date: string;
  summary: string;
  content: string;
  originalUrl: string;
  category: string;
}

export const mockArticles: Article[] = [
  {
    id: "1",
    title: "New Climate Legislation Passes House with Bipartisan Support",
    source: "Reuters",
    bias: "center",
    trustScore: 92,
    date: "2026-03-24",
    category: "Politics",
    summary: "The House of Representatives passed new climate legislation with support from both parties. The bill includes provisions for renewable energy incentives, carbon capture research funding, and new emissions standards for industrial facilities. The vote was 278-157, with 45 Republicans joining Democrats in support.",
    content: "In a rare show of bipartisan cooperation, the House passed comprehensive climate legislation that aims to reduce carbon emissions by 40% over the next decade. The bill allocates $200 billion for renewable energy infrastructure and provides tax incentives for both businesses and individuals who adopt clean energy solutions.",
    originalUrl: "https://reuters.com/example-article-1"
  },
  {
    id: "2",
    title: "Climate Bill: A Victory for Green Energy and American Jobs",
    source: "MSNBC",
    bias: "left",
    trustScore: 78,
    date: "2026-03-24",
    category: "Politics",
    summary: "Progressive lawmakers celebrated the passage of landmark climate legislation, calling it a major step toward environmental justice. The bill is expected to create millions of green jobs while addressing the urgent climate crisis. Environmental groups praised the legislation as long overdue.",
    content: "Today marks a turning point in the fight against climate change. The new legislation not only addresses the climate emergency but also prioritizes environmental justice for communities that have been disproportionately affected by pollution. This is the bold action we've needed for decades.",
    originalUrl: "https://msnbc.com/example-article-2"
  },
  {
    id: "3",
    title: "House Climate Bill Raises Concerns Over Economic Impact",
    source: "Fox Business",
    bias: "right",
    trustScore: 74,
    date: "2026-03-24",
    category: "Politics",
    summary: "Business leaders and conservative lawmakers expressed concerns about the economic impact of the newly passed climate legislation. Critics argue the bill's regulations could burden small businesses and increase energy costs for consumers. The Chamber of Commerce warned of potential job losses in traditional energy sectors.",
    content: "While proponents tout job creation in renewable energy, the reality is more complex. The legislation imposes strict regulations that could force energy-intensive industries to relocate overseas, taking American jobs with them. Small business owners worry about the cost of compliance.",
    originalUrl: "https://foxbusiness.com/example-article-3"
  },
  {
    id: "4",
    title: "Federal Reserve Holds Interest Rates Steady, Signals Future Cuts",
    source: "Wall Street Journal",
    bias: "center",
    trustScore: 89,
    date: "2026-03-23",
    category: "Economy",
    summary: "The Federal Reserve kept interest rates unchanged at its latest meeting but indicated potential rate cuts later this year. Fed Chair Jerome Powell cited cooling inflation and stable employment as factors in the decision. Market analysts predict two quarter-point cuts by year-end.",
    content: "The Federal Open Market Committee voted unanimously to maintain the federal funds rate at 4.5%-4.75%. Chair Powell emphasized the Fed's data-dependent approach, noting that while inflation has moderated significantly, policymakers want to ensure price stability before easing monetary policy.",
    originalUrl: "https://wsj.com/example-article-4"
  },
  {
    id: "5",
    title: "Fed's Dovish Tone Signals Relief for Working Families",
    source: "The Nation",
    bias: "left",
    trustScore: 72,
    date: "2026-03-23",
    category: "Economy",
    summary: "The Federal Reserve's decision to hold rates and signal future cuts offers hope for working families struggling with high borrowing costs. Economic justice advocates argue that earlier rate cuts could have prevented unnecessary hardship for low-income households. The Fed must prioritize employment over inflation fears.",
    content: "For too long, the Fed's aggressive rate hiking campaign has punished working people while corporate profits soared. Today's dovish signal is welcome, but it comes late for families who lost homes or jobs. The central bank must remember that employment is part of its dual mandate.",
    originalUrl: "https://thenation.com/example-article-5"
  },
  {
    id: "6",
    title: "Interest Rate Stability Demonstrates Fed's Cautious Approach",
    source: "American Enterprise Institute",
    bias: "lean-right",
    trustScore: 81,
    date: "2026-03-23",
    category: "Economy",
    summary: "The Federal Reserve's decision to maintain current rates reflects a prudent approach to monetary policy. Economists at conservative think tanks applaud the Fed's patience, warning that premature rate cuts could reignite inflation. Strong economic fundamentals support the current wait-and-see strategy.",
    content: "The Fed's steady hand demonstrates institutional wisdom. With the economy growing at a healthy pace and employment robust, there's no urgency to cut rates. Maintaining current policy allows the Fed to ensure inflation remains under control while avoiding the boom-bust cycles of the past.",
    originalUrl: "https://aei.org/example-article-6"
  },
  {
    id: "7",
    title: "Tech Giants Face New Antitrust Legislation in Senate",
    source: "Associated Press",
    bias: "center",
    trustScore: 94,
    date: "2026-03-22",
    category: "Technology",
    summary: "A bipartisan group of senators introduced comprehensive antitrust legislation targeting major tech companies. The bill would restrict acquisitions by dominant platforms, require data portability, and increase merger scrutiny. Both progressive and conservative senators support the measure, though industry groups oppose it.",
    content: "Senators from both parties unveiled the Platform Competition and Opportunity Act, which aims to prevent anti-competitive behavior by large tech companies. The legislation has support from a coalition that includes both Elizabeth Warren and Josh Hawley, reflecting broad concern about tech monopolies.",
    originalUrl: "https://apnews.com/example-article-7"
  },
  {
    id: "8",
    title: "Finally, Congress Takes on Big Tech Monopolies",
    source: "The Guardian",
    bias: "lean-left",
    trustScore: 80,
    date: "2026-03-22",
    category: "Technology",
    summary: "Progressive advocates celebrated new antitrust legislation aimed at breaking up tech monopolies and protecting consumer rights. The bill addresses years of unchecked corporate power and data exploitation. Consumer protection groups call it a crucial first step toward digital rights and privacy protection.",
    content: "For years, tech giants have operated with impunity, crushing competition and exploiting user data for profit. This legislation represents a long-overdue reckoning. By restricting predatory acquisitions and requiring data portability, Congress is finally putting people over corporate interests.",
    originalUrl: "https://theguardian.com/example-article-8"
  },
  {
    id: "9",
    title: "Antitrust Bill Threatens American Tech Innovation",
    source: "National Review",
    bias: "right",
    trustScore: 76,
    date: "2026-03-22",
    category: "Technology",
    summary: "New antitrust legislation targeting tech companies could undermine American innovation and competitiveness. Industry experts warn that restricting acquisitions will prevent startups from achieving exits, ultimately harming the entrepreneurial ecosystem. The bill may benefit foreign competitors at America's expense.",
    content: "While concerns about tech monopolies are valid, this heavy-handed legislation threatens to throw out the baby with the bathwater. The ability of large platforms to acquire innovative startups has been a driver of American tech dominance. Bureaucratic oversight of mergers will slow innovation and help Chinese competitors.",
    originalUrl: "https://nationalreview.com/example-article-9"
  },
  {
    id: "10",
    title: "Supreme Court to Hear Major Voting Rights Case",
    source: "NPR",
    bias: "center",
    trustScore: 91,
    date: "2026-03-21",
    category: "Politics",
    summary: "The Supreme Court agreed to hear a significant voting rights case involving state redistricting practices. The case could have major implications for how states draw congressional districts and whether certain practices constitute racial gerrymandering. Oral arguments are scheduled for next term.",
    content: "The Court will review a lower court decision that struck down a state's congressional map as unconstitutional racial gerrymandering. The case tests the limits of the Voting Rights Act and could reshape redistricting nationwide. Both civil rights groups and state officials are closely watching the proceedings.",
    originalUrl: "https://npr.org/example-article-10"
  },
  {
    id: "11",
    title: "Supreme Court Poised to Protect Voting Rights",
    source: "Mother Jones",
    bias: "left",
    trustScore: 69,
    date: "2026-03-21",
    category: "Politics",
    summary: "Civil rights advocates express cautious optimism as the Supreme Court takes up a crucial voting rights case. The case represents a critical test of whether the Court will uphold protections against racial discrimination in voting. Recent decisions have weakened voting rights, making this case even more significant.",
    content: "After years of the Court gutting voting protections, this case offers a chance for redemption. Communities of color have faced systematic disenfranchisement through gerrymandering and voter suppression. The Court must stand on the side of democracy and equal representation.",
    originalUrl: "https://motherjones.com/example-article-11"
  },
  {
    id: "12",
    title: "Court's Voting Case Could Limit State Sovereignty",
    source: "Washington Examiner",
    bias: "lean-right",
    trustScore: 73,
    date: "2026-03-21",
    category: "Politics",
    summary: "Constitutional scholars debate the implications of a new Supreme Court voting rights case. Some argue that federal courts have overreached in striking down state redistricting plans. The case raises important questions about federalism and states' constitutional authority to manage their own elections.",
    content: "The Constitution grants states significant authority over election administration. Federal courts should exercise restraint before overturning state legislative decisions. While protecting voting rights is important, federal judges shouldn't micromanage every redistricting decision based on partisan considerations.",
    originalUrl: "https://washingtonexaminer.com/example-article-12"
  }
];

export function getArticleById(id: string): Article | undefined {
  return mockArticles.find(article => article.id === id);
}

export function getArticlesByBias(bias: BiasRating): Article[] {
  return mockArticles.filter(article => article.bias === bias);
}
