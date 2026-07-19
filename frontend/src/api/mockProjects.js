// MOCK — see STATUS.md
// This file serves as the mock database for projects until the repository API is implemented.

export const mockProjects = [
  {
    id: "1",
    title: "AI-Powered Undergraduate Project Discovery and Knowledge Retrieval Platform",
    authors: [
      { name: "Sarthak Shrestha", rollNumber: "PUL076BCT024", email: "sarthak@ioe.edu.np" },
      { name: "Anish Pandey", rollNumber: "PUL076BCT008", email: "anish@ioe.edu.np" },
      { name: "Bidhyanand Lal", rollNumber: "PUL076BCT015", email: "bidhya@ioe.edu.np" }
    ],
    supervisor: "Prof. Dr. Subarna Shakya",
    year: "2080",
    department: "DOECE",
    cluster: "AIML",
    status: "approved",
    abstract: "The rapid growth of undergraduate engineering projects at Pulchowk Campus has made it difficult for students and faculty to discover prior work, leading to duplication and inefficiencies. This project presents a semantic discovery and retrieval platform powered by LLMs and RAG. By leveraging pgvector for dense embedding storage, PyMuPDF for document ingestion, and a custom search pipeline, the platform allows natural language queries to search across a comprehensive archive of student theses. We demonstrate significant improvements in relevance and response times compared to traditional keyword-based digital repositories.",
    resultsSummary: "1. Achieved 94% accuracy in metadata auto-extraction from PDF title pages.\n2. Reduced project search discovery time by 75% compared to keyword-based OPAC catalog queries.\n3. Successfully indexed over 3 years of DOECE undergraduate thesis archives into a pgvector store.\n4. Deployed a conversational RAG chat grounded exclusively in approved project abstracts.",
    technologies: ["Django", "React", "pgvector", "PyMuPDF", "SentenceTransformers", "Vite", "TailwindCSS"],
    coverImage: "https://images.unsplash.com/photo-1544383835-bda2bc66a55d?auto=format&fit=crop&q=80&w=600",
    pdfUrl: "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  },
  {
    id: "2",
    title: "Autonomous Drone Navigation in GPS-Denied Environments Using Visual SLAM",
    authors: [
      { name: "Ramesh Thapa", rollNumber: "PUL077BCT045", email: "ramesh@ioe.edu.np" },
      { name: "Sita Devkota", rollNumber: "PUL077BCT052", email: "sita@ioe.edu.np" }
    ],
    supervisor: "Assoc. Prof. Dr. Surendra Shrestha",
    year: "2081",
    department: "DOECE",
    cluster: "Robotics",
    status: "pending",
    abstract: "Autonomous navigation in GPS-denied environments like indoor warehouses or deep valleys remains a major challenge in robotics. This project presents a vision-based Simultaneous Localization and Mapping (vSLAM) solution deployed on an custom quadcopter. Using an onboard stereo camera, ORB-SLAM3 algorithms build a sparse 3D map of the environment, enabling real-time drift-free positioning. The navigation stack includes active obstacle avoidance using OctoMap and path planning via A* search, demonstrating reliable autonomous waypoint navigation inside the Pulchowk BCT labs.",
    resultsSummary: "1. Stabilized drift to under 5cm per meter of autonomous flight inside indoor environments.\n2. Built dynamic 3D voxel maps using OctoMap on an onboard companion computer (Raspberry Pi 4).\n3. Verified real-time obstacle avoidance with a response delay of less than 120ms.",
    technologies: ["ROS Noetic", "ORB-SLAM3", "C++", "Python", "Raspberry Pi", "OctoMap"],
    coverImage: "https://images.unsplash.com/photo-1508614589041-895b88991e3e?auto=format&fit=crop&q=80&w=600",
    pdfUrl: "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  },
  {
    id: "3",
    title: "Blockchain-Based Decentralized Identity Management for Academic Verification",
    authors: [
      { name: "Kiran KC", rollNumber: "PUL075BCT012", email: "kiran@ioe.edu.np" },
      { name: "Pooja Acharya", rollNumber: "PUL075BCT030", email: "" } // Example with no author email
    ],
    supervisor: "Er. Sharad Kumar Ghimire",
    year: "2079",
    department: "DOECE",
    cluster: "Software Engineering",
    status: "rejected",
    abstract: "Verification of academic transcripts, recommendations, and degrees is a manual and fraud-prone process. This project implements a decentralized identity (DID) management system built on Ethereum. Students own their digital identity documents, which are cryptographic signed by the IOE administration. Using smart contracts and IPFS, external verifiers (e.g., foreign universities, employers) can instantaneously verify the authenticity of a degree without contacting the campus database, maintaining user privacy and preventing document forgery.",
    resultsSummary: "1. Designed Solidity smart contracts running on Ethereum testnets with gas-optimized verification cycles.\n2. Formulated self-sovereign identity credentials conforming to W3C DID standards.\n3. Eliminated academic verification latency from weeks to under 10 seconds.",
    technologies: ["Solidity", "Ethereum", "IPFS", "Web3.js", "React", "Node.js"],
    coverImage: "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?auto=format&fit=crop&q=80&w=600",
    pdfUrl: "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }
];

export const getProjectById = (id) => {
  return mockProjects.find((p) => p.id === id) || null;
};
