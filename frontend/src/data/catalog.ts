import type { GenerateRequest, ModelChoice, VideoType } from '../types/script';

// ── Catalog types ──────────────────────────────────────────────────────────

export interface CatalogSection {
  n: string;
  t: string;
}

export interface CatalogChapter {
  n: string;
  unit?: number;
  name: string;
  secs: CatalogSection[];
}

export interface CatalogBook {
  id: string;
  title: string;
  sub: string;
  color: string;
  bookTitle: string;
  chapters: CatalogChapter[];
}

// ── Full OpenStax catalog ──────────────────────────────────────────────────

export const CATALOG: CatalogBook[] = [
  // ─── Nursing ───
  {
    id: 'nursingfund', title: 'Fundamentals of Nursing', sub: 'OpenStax Nursing', color: '#d35400',
    bookTitle: 'Fundamentals of Nursing',
    chapters: [
      { n: '01', unit: 1, name: 'Nursing: Past, Present, and Future', secs: [{ n: '1.1', t: 'Evolution of Nursing and Nursing Practice' }, { n: '1.2', t: 'Nursing Education Programs' }, { n: '1.3', t: 'Nursing as a Profession' }, { n: '1.4', t: 'History and Evolution of Nursing Theories' }, { n: '1.5', t: 'Selected Nursing Theorist' }, { n: '1.6', t: 'Application of Theories in Nursing Practice' }] },
      { n: '02', unit: 1, name: 'Communication', secs: [{ n: '2.1', t: 'Introduction to Communication' }, { n: '2.2', t: 'Therapeutic Communication' }, { n: '2.3', t: 'Barriers to Communication' }, { n: '2.4', t: 'Communication Across the Lifespan' }, { n: '2.5', t: 'Communicating with Patients with Special Needs' }] },
      { n: '05', unit: 2, name: 'Clinical Safety', secs: [{ n: '5.1', t: 'Introduction to Clinical Safety' }, { n: '5.2', t: 'Fall Prevention' }, { n: '5.3', t: 'Restraints' }, { n: '5.4', t: 'Fire Safety' }, { n: '5.5', t: 'Safe Handling and Disposal of Sharps' }] },
      { n: '09', unit: 3, name: 'Vital Signs', secs: [{ n: '9.1', t: 'Introduction to Vital Signs' }, { n: '9.2', t: 'Temperature' }, { n: '9.3', t: 'Pulse' }, { n: '9.4', t: 'Respirations' }, { n: '9.5', t: 'Blood Pressure' }, { n: '9.6', t: 'Oxygen Saturation' }] },
      { n: '14', unit: 4, name: 'Medication Administration', secs: [{ n: '14.1', t: 'Introduction to Medication Administration' }, { n: '14.2', t: 'Rights of Medication Administration' }, { n: '14.3', t: 'Oral Medications' }, { n: '14.4', t: 'Parenteral Medications' }, { n: '14.5', t: 'Topical Medications' }] },
    ],
  },
  {
    id: 'clinicalnursing', title: 'Clinical Nursing Skills', sub: 'OpenStax Nursing', color: '#c0392b',
    bookTitle: 'Clinical Nursing Skills',
    chapters: [
      { n: '01', unit: 1, name: 'The Role of the Nurse in Comprehensive Care', secs: [{ n: '1.1', t: 'Principles of Nursing Practice' }, { n: '1.2', t: 'Evidence-Based Practice' }, { n: '1.3', t: 'Nursing Process' }] },
      { n: '02', unit: 1, name: "The Evolution of the Nurse's Role", secs: [{ n: '2.1', t: 'Changing with Trends' }, { n: '2.2', t: 'Patient-Centered Care' }, { n: '2.3', t: 'Practice Standards' }, { n: '2.4', t: 'Collaborative Care' }] },
      { n: '03', unit: 1, name: 'Patient Communication and Interviewing', secs: [{ n: '3.1', t: 'Therapeutic Communication' }, { n: '3.2', t: 'Comprehensive Interview Practices' }, { n: '3.3', t: 'Patient Education and Teaching' }] },
      { n: '04', unit: 1, name: 'Obtaining a Complete Health History', secs: [{ n: '4.1', t: 'Foundations for a Complete Electronic Health Record' }, { n: '4.2', t: 'Data Collection and Documentation' }, { n: '4.3', t: 'Informatics' }] },
      { n: '05', unit: 1, name: 'Cultural Competence and Assessment', secs: [{ n: '5.1', t: 'Understanding Cultural Differences' }, { n: '5.2', t: 'Ethical Practice in Culture and Diversity' }, { n: '5.3', t: 'Cultural Practice in Nursing' }, { n: '5.4', t: 'Diversity, Equity, and Inclusion' }] },
      { n: '06', unit: 1, name: 'Infection Prevention Techniques and Safety', secs: [{ n: '6.1', t: 'Infection Cycle' }, { n: '6.2', t: 'Asepsis and PPE' }, { n: '6.3', t: 'Sterile Technique' }, { n: '6.4', t: 'Infection Control and Patient Safety' }] },
      { n: '07', unit: 2, name: 'Hygiene', secs: [{ n: '7.1', t: 'Hygiene Practices' }, { n: '7.2', t: 'Factors Influencing Personal Hygiene' }, { n: '7.3', t: 'Assisting with Hygiene and Health Promotion' }] },
      { n: '08', unit: 2, name: 'Wound and Burn Assessment and Care', secs: [{ n: '8.1', t: 'Wound Classification' }, { n: '8.2', t: 'Wound Assessment' }, { n: '8.3', t: 'Wound Management' }, { n: '8.4', t: 'Burn Injuries and Management' }] },
      { n: '09', unit: 2, name: 'Activity Assessment and Management', secs: [{ n: '9.1', t: 'Assessing Functional Ability' }, { n: '9.2', t: 'Assessing Mobility' }, { n: '9.3', t: 'Transferring Patients' }, { n: '9.4', t: 'Positioning in Bed' }, { n: '9.5', t: 'Limited Movement Devices' }] },
      { n: '10', unit: 2, name: 'Specimen Collection and Lab Testing', secs: [{ n: '10.1', t: 'Urine Specimen' }, { n: '10.2', t: 'Stool Collection' }, { n: '10.3', t: 'Sputum Collection' }, { n: '10.4', t: 'Blood Sampling' }] },
      { n: '11', unit: 3, name: 'Principles of Medication Administration', secs: [{ n: '11.1', t: 'Rights of Medication Administration' }, { n: '11.2', t: 'Dosing' }, { n: '11.3', t: 'Documentation of Medication Administration' }] },
      { n: '12', unit: 3, name: 'Medication Administration Procedures', secs: [{ n: '12.1', t: 'Administering Oral Medications' }, { n: '12.2', t: 'Administering Parenteral Medications' }, { n: '12.3', t: 'Preparing Unit-Dose Packaged Medications' }, { n: '12.4', t: 'Administering Intradermal Injections' }, { n: '12.5', t: 'Administering Subcutaneous Injections' }, { n: '12.6', t: 'Administering Intramuscular Injections' }] },
      { n: '13', unit: 3, name: 'Intravenous Administration', secs: [{ n: '13.1', t: 'Principles of Intravenous Therapy' }, { n: '13.2', t: 'Intravenous Device Insertion' }, { n: '13.3', t: 'Intravenous Infusion' }, { n: '13.4', t: 'Blood Transfusions' }] },
      { n: '14', unit: 3, name: 'Miscellaneous Medication Administration', secs: [{ n: '14.1', t: 'Administering Eye Medications' }, { n: '14.2', t: 'Administering Ear Medications' }, { n: '14.3', t: 'Administering Nasal Medications' }, { n: '14.4', t: 'Administering Inhaled Medications' }, { n: '14.5', t: 'Administering Other Medications' }] },
      { n: '15', unit: 4, name: 'General Survey, Anthropometric Measurement, and Vital Signs', secs: [{ n: '15.1', t: 'Performing a General Survey' }, { n: '15.2', t: 'Common Types of Anthropometric Measurements' }, { n: '15.3', t: 'Vital Signs' }, { n: '15.4', t: 'Temperature' }, { n: '15.5', t: 'Heart Rate' }, { n: '15.6', t: 'Respiration' }, { n: '15.7', t: 'Blood Pressure' }] },
      { n: '16', unit: 4, name: 'Pain Assessment', secs: [{ n: '16.1', t: 'The Pain Process' }, { n: '16.2', t: 'Responses to Pain' }, { n: '16.3', t: 'Factors Affecting Pain' }, { n: '16.4', t: 'Pain Assessment' }, { n: '16.5', t: 'Pain Management' }] },
      { n: '17', unit: 4, name: 'Nutrition Assessment', secs: [{ n: '17.1', t: 'Nutritional Concepts' }, { n: '17.2', t: 'Factors Affecting Nutrition' }, { n: '17.3', t: 'Specialized Diets' }, { n: '17.4', t: 'Nutritional Assessment' }] },
      { n: '18', unit: 4, name: 'Oxygenation and Perfusion', secs: [{ n: '18.1', t: 'Respiratory System' }, { n: '18.2', t: 'Cardiovascular System' }, { n: '18.3', t: 'Factors Affecting Cardiopulmonary Function' }, { n: '18.4', t: 'Management of Impaired Cardiopulmonary Functioning' }] },
      { n: '19', unit: 4, name: 'Fluids, Electrolytes, and Elimination', secs: [{ n: '19.1', t: 'Fluid and Electrolytes' }, { n: '19.2', t: 'Nursing Assessment for Fluid and Electrolytes' }, { n: '19.3', t: 'Considerations for Fluid and Electrolyte Imbalances' }, { n: '19.4', t: 'Nursing Management of Elimination' }] },
      { n: '20', unit: 4, name: 'Psychosocial Assessment', secs: [{ n: '20.1', t: 'Mental Health Assessment' }, { n: '20.2', t: 'Substance Use Disorder Assessment' }, { n: '20.3', t: 'Abuse and Neglect Assessment' }] },
      { n: '21', unit: 4, name: 'Assessment of the Integumentary System', secs: [{ n: '21.1', t: 'Structure and Functions of the Skin' }, { n: '21.2', t: 'Factors Affecting Skin Integrity' }] },
      { n: '22', unit: 4, name: 'Assessment of the Head and Neck', secs: [{ n: '22.1', t: 'Head and Neck' }, { n: '22.2', t: 'Eyes' }, { n: '22.3', t: 'Ears' }, { n: '22.4', t: 'Mouth, Throat, Nose, and Sinuses' }] },
      { n: '23', unit: 4, name: 'Assessment of the Thorax, Lungs, Breast, and Lymphatic System', secs: [{ n: '23.1', t: 'Structure and Function' }, { n: '23.2', t: 'Physical Assessment of the Thorax' }, { n: '23.3', t: 'Breath Sounds and Lung Assessment' }, { n: '23.4', t: 'Breast and Lymphatic System' }] },
      { n: '24', unit: 4, name: 'Assessment of the Cardiovascular and Peripheral Vascular System', secs: [{ n: '24.1', t: 'Cardiovascular System' }, { n: '24.2', t: 'Peripheral Vascular System' }, { n: '24.3', t: 'Nursing Assessment' }] },
      { n: '25', unit: 4, name: 'Assessment of the Musculoskeletal System', secs: [{ n: '25.1', t: 'Structure and Function' }, { n: '25.2', t: 'Physical Assessment' }, { n: '25.3', t: 'Recognizing Common Musculoskeletal Disorders' }] },
      { n: '26', unit: 4, name: 'Assessment of the Neurological System', secs: [{ n: '26.1', t: 'Structure and Function' }, { n: '26.2', t: 'Physical Assessment' }, { n: '26.3', t: 'Recognizing Common Neurological Disorders' }] },
      { n: '27', unit: 4, name: 'Assessment of the Abdomen', secs: [{ n: '27.1', t: 'Structure and Function' }, { n: '27.2', t: 'Physical Assessment' }, { n: '27.3', t: 'Recognizing Common Abdominal Disorders' }] },
      { n: '28', unit: 4, name: 'Clinical Judgment and Critical Thinking', secs: [{ n: '28.1', t: 'Clinical Judgment Measurement Model' }, { n: '28.2', t: 'Developing Critical Thinking Skills' }, { n: '28.3', t: 'Unfolding Case Study Dissection' }] },
    ],
  },
  {
    id: 'maternalnursing', title: 'Maternal-Newborn Nursing', sub: 'OpenStax Nursing', color: '#8e44ad',
    bookTitle: 'Maternal-Newborn Nursing',
    chapters: [
      { n: '01', unit: 1, name: "Foundations in Maternal-Newborn and Women's Health Nursing", secs: [{ n: '1.1', t: "Current Trends in Women's Health Care" }, { n: '1.2', t: 'Standards of Maternal, Newborn, and Gynecologic Nursing Care' }, { n: '1.3', t: 'Perinatal Care: Regional and Levels of Care and Transport' }, { n: '1.4', t: 'Ethical and Legal Concerns' }] },
      { n: '02', unit: 1, name: 'Culturally Competent Nursing Care', secs: [{ n: '2.1', t: 'Person- and Family-Centered Care' }, { n: '2.2', t: 'Family Health and Cultural Factors' }, { n: '2.3', t: 'Culturally Competent Care' }, { n: '2.4', t: 'Families at Higher Risk for Poor Health Outcomes' }] },
      { n: '10', unit: 3, name: 'Pregnancy', secs: [{ n: '10.1', t: 'Physiologic Changes Due to Pregnancy' }, { n: '10.2', t: 'Psychosocial Aspects of Pregnancy' }, { n: '10.3', t: 'Common Discomforts of Pregnancy' }, { n: '10.4', t: 'Fetal Growth and Development' }] },
      { n: '15', unit: 4, name: 'Process of Labor and Birth', secs: [{ n: '15.1', t: 'Factors Influencing the Process of Labor and Birth' }, { n: '15.2', t: 'Stages of Labor' }, { n: '15.3', t: 'Physiologic Adaptations during Labor and Birth' }] },
      { n: '22', unit: 6, name: 'Immediate Care of the Newborn', secs: [{ n: '22.1', t: 'Apgar Scoring' }, { n: '22.2', t: 'Physiological Adaptation and Transition' }, { n: '22.3', t: 'Neutral Thermal Environment' }] },
    ],
  },
  {
    id: 'medsurgnursing', title: 'Medical-Surgical Nursing', sub: 'OpenStax Nursing', color: '#1a5276',
    bookTitle: 'Medical-Surgical Nursing',
    chapters: [
      { n: '01', unit: 1, name: 'Professional Medical-Surgical Nursing', secs: [{ n: '1.1', t: 'Professional Nursing Practice' }, { n: '1.2', t: 'Intercollaborative Care' }, { n: '1.3', t: 'Health Policy and Ethical Considerations' }, { n: '1.4', t: 'Evidence-Based Practice' }] },
      { n: '06', unit: 3, name: 'Comprehensive Health Assessment and Physical Examination', secs: [{ n: '6.1', t: 'Critical Thinking in Assessment' }, { n: '6.2', t: 'Effective Communication in the Nurse-Patient Relationship' }, { n: '6.3', t: 'Health History' }, { n: '6.4', t: 'Bedside Physical Assessment in Medical-Surgical Nursing' }] },
      { n: '12', unit: 4, name: 'Cardiovascular System', secs: [{ n: '12.1', t: 'Cardiovascular Overview' }, { n: '12.2', t: 'Dysrhythmia' }, { n: '12.3', t: 'Heart Failure' }, { n: '12.4', t: 'Hypertension' }, { n: '12.5', t: 'Myocardial Infarction' }] },
      { n: '21', unit: 4, name: 'Endocrine System and Disorders', secs: [{ n: '21.1', t: 'Endocrine Anatomy and Physiology' }, { n: '21.2', t: 'Diabetes Mellitus' }, { n: '21.3', t: 'Thyroid and Parathyroid Disorders' }] },
      { n: '31', unit: 6, name: 'Cancer', secs: [{ n: '31.1', t: 'Oncological Disorders' }, { n: '31.2', t: 'Detection and Prevention of Cancer' }, { n: '31.3', t: 'Care of the Patient with Cancer' }, { n: '31.4', t: 'Survivorship' }] },
    ],
  },

  // ─── Life Sciences ───
  {
    id: 'biology2e', title: 'Biology 2e', sub: 'Clark · Douglas · Choi', color: '#9ccb3b',
    bookTitle: 'Biology 2e',
    chapters: [
      { n: '01', unit: 1, name: 'The Study of Life', secs: [{ n: '1.1', t: 'The Science of Biology' }, { n: '1.2', t: 'Themes and Concepts of Biology' }] },
      { n: '02', unit: 1, name: 'The Chemical Foundation of Life', secs: [{ n: '2.1', t: 'Atoms, Isotopes, Ions, and Molecules' }, { n: '2.2', t: 'Water' }, { n: '2.3', t: 'Carbon' }] },
      { n: '03', unit: 1, name: 'Biological Macromolecules', secs: [{ n: '3.1', t: 'Synthesis of Biological Macromolecules' }, { n: '3.2', t: 'Carbohydrates' }, { n: '3.3', t: 'Lipids' }, { n: '3.4', t: 'Proteins' }, { n: '3.5', t: 'Nucleic Acids' }] },
      { n: '05', unit: 2, name: 'Structure and Function of Plasma Membranes', secs: [{ n: '5.1', t: 'Components and Structure' }, { n: '5.2', t: 'Passive Transport' }, { n: '5.3', t: 'Active Transport' }, { n: '5.4', t: 'Bulk Transport' }] },
      { n: '09', unit: 2, name: 'Cellular Respiration', secs: [{ n: '9.1', t: 'Energy in Living Systems' }, { n: '9.2', t: 'Glycolysis' }, { n: '9.3', t: 'Citric Acid Cycle' }, { n: '9.4', t: 'Oxidative Phosphorylation' }] },
      { n: '10', unit: 2, name: 'Photosynthesis', secs: [{ n: '10.1', t: 'Overview of Photosynthesis' }, { n: '10.2', t: 'The Light-Dependent Reactions' }, { n: '10.3', t: 'Using Light Energy to Make Organic Molecules' }] },
      { n: '11', unit: 3, name: 'Meiosis and Sexual Reproduction', secs: [{ n: '11.1', t: 'The Process of Meiosis' }, { n: '11.2', t: 'Sexual Reproduction' }] },
      { n: '14', unit: 3, name: 'DNA Structure and Function', secs: [{ n: '14.1', t: 'Historical Basis of Modern Understanding' }, { n: '14.2', t: 'DNA Structure and Sequencing' }, { n: '14.3', t: 'Basics of DNA Replication' }, { n: '14.4', t: 'DNA Replication in Prokaryotes' }, { n: '14.5', t: 'DNA Replication in Eukaryotes' }, { n: '14.6', t: 'DNA Repair' }] },
    ],
  },
  {
    id: 'anatomy', title: 'Anatomy and Physiology 2e', sub: 'Betts · Young · Wise', color: '#e74c3c',
    bookTitle: 'Anatomy and Physiology 2e',
    chapters: [
      { n: '01', unit: 1, name: 'An Introduction to the Human Body', secs: [{ n: '1.1', t: 'Overview of Anatomy and Physiology' }, { n: '1.2', t: 'Structural Organization of the Human Body' }, { n: '1.3', t: 'Functions of Human Life' }, { n: '1.5', t: 'Homeostasis' }, { n: '1.6', t: 'Anatomical Terminology' }] },
      { n: '03', unit: 1, name: 'The Cellular Level of Organization', secs: [{ n: '3.1', t: 'The Cell Membrane' }, { n: '3.2', t: 'The Cytoplasm and Cellular Organelles' }, { n: '3.3', t: 'The Nucleus and DNA Replication' }, { n: '3.4', t: 'Protein Synthesis' }, { n: '3.5', t: 'Cell Growth and Division' }] },
      { n: '12', unit: 3, name: 'The Nervous System and Nervous Tissue', secs: [{ n: '12.1', t: 'Basic Structure and Function of the Nervous System' }, { n: '12.2', t: 'Nervous Tissue' }, { n: '12.3', t: 'The Function of Nervous Tissue' }, { n: '12.4', t: 'The Action Potential' }, { n: '12.5', t: 'Communication Between Neurons' }] },
      { n: '22', unit: 5, name: 'The Respiratory System', secs: [{ n: '22.1', t: 'Organs and Structures of the Respiratory System' }, { n: '22.2', t: 'The Lungs' }, { n: '22.3', t: 'The Process of Breathing' }, { n: '22.4', t: 'Gas Exchange' }, { n: '22.5', t: 'Transport of Gases' }] },
    ],
  },
  {
    id: 'microbio', title: 'Microbiology', sub: 'Parker · Schneegurt · Thi Tu', color: '#27ae60',
    bookTitle: 'Microbiology',
    chapters: [
      { n: '01', unit: 1, name: 'An Invisible World', secs: [{ n: '1.1', t: 'A Invisible World' }, { n: '1.2', t: 'A Brief History of Microbiology' }, { n: '1.3', t: 'Types of Microorganisms' }] },
      { n: '09', unit: 3, name: 'Microbial Growth', secs: [{ n: '9.1', t: 'How Microbes Grow' }, { n: '9.2', t: 'Oxygen Requirements for Microbial Growth' }, { n: '9.3', t: 'The Effects of pH on Microbial Growth' }, { n: '9.4', t: 'Temperature and Microbial Growth' }] },
      { n: '15', unit: 5, name: 'Microbial Mechanisms of Pathogenicity', secs: [{ n: '15.1', t: 'Characteristics of Infectious Disease' }, { n: '15.2', t: 'How Pathogens Cause Disease' }, { n: '15.3', t: 'Virulence Factors of Bacterial and Viral Pathogens' }, { n: '15.4', t: 'Virulence Factors of Eukaryotic Animal Pathogens' }] },
    ],
  },
  {
    id: 'conceptsbio', title: 'Concepts of Biology', sub: 'Fowler · Roush · Wise', color: '#52be80',
    bookTitle: 'Concepts of Biology',
    chapters: [
      { n: '01', unit: 1, name: 'Introduction to Biology', secs: [{ n: '1.1', t: 'Themes and Concepts of Biology' }, { n: '1.2', t: 'The Process of Science' }, { n: '1.3', t: 'The Diversity of Life' }] },
      { n: '04', unit: 2, name: 'How Cells Obtain Energy', secs: [{ n: '4.1', t: 'Energy and Metabolism' }, { n: '4.2', t: 'Glycolysis' }, { n: '4.3', t: 'Citric Acid Cycle and Oxidative Phosphorylation' }, { n: '4.4', t: 'Fermentation' }, { n: '4.5', t: 'Connections to Other Metabolic Pathways' }] },
    ],
  },

  // ─── Physical Sciences ───
  {
    id: 'chem2e', title: 'Chemistry 2e', sub: 'Flowers · Theopold · Langley', color: '#f36f21',
    bookTitle: 'Chemistry 2e',
    chapters: [
      { n: '01', unit: 1, name: 'Essential Ideas', secs: [{ n: '1.1', t: 'Chemistry in Context' }, { n: '1.2', t: 'Phases and Classification of Matter' }, { n: '1.3', t: 'Physical and Chemical Properties' }, { n: '1.4', t: 'Measurements' }, { n: '1.5', t: 'Measurement Uncertainty, Accuracy, and Precision' }] },
      { n: '07', unit: 2, name: 'Chemical Bonding and Molecular Geometry', secs: [{ n: '7.1', t: 'Ionic Bonding' }, { n: '7.2', t: 'Covalent Bonding' }, { n: '7.3', t: 'Lewis Symbols and Structures' }, { n: '7.4', t: 'Formal Charges and Resonance' }, { n: '7.5', t: 'Strengths of Ionic and Covalent Bonds' }] },
      { n: '12', unit: 3, name: 'Kinetics', secs: [{ n: '12.1', t: 'Chemical Reaction Rates' }, { n: '12.2', t: 'Factors Affecting Reaction Rates' }, { n: '12.3', t: 'Rate Laws' }, { n: '12.4', t: 'Integrated Rate Laws' }, { n: '12.5', t: 'Collision Theory' }] },
    ],
  },
  {
    id: 'physics1', title: 'University Physics Vol. 1', sub: 'Ling · Sanny · Moebs', color: '#002569',
    bookTitle: 'University Physics Volume 1',
    chapters: [
      { n: '03', unit: 1, name: 'Motion Along a Straight Line', secs: [{ n: '3.1', t: 'Position, Displacement, and Average Velocity' }, { n: '3.2', t: 'Instantaneous Velocity and Speed' }, { n: '3.3', t: 'Average and Instantaneous Acceleration' }, { n: '3.4', t: 'Motion with Constant Acceleration' }, { n: '3.5', t: 'Free Fall' }] },
      { n: '05', unit: 1, name: "Newton's Laws of Motion", secs: [{ n: '5.1', t: 'Forces' }, { n: '5.2', t: "Newton's First Law" }, { n: '5.3', t: "Newton's Second Law" }, { n: '5.4', t: 'Mass and Weight' }, { n: '5.5', t: "Newton's Third Law" }] },
      { n: '08', unit: 2, name: 'Potential Energy and Conservation of Energy', secs: [{ n: '8.1', t: 'Potential Energy of a System' }, { n: '8.2', t: 'Conservative and Non-Conservative Forces' }, { n: '8.3', t: 'Conservation of Energy' }, { n: '8.4', t: 'Potential Energy Diagrams and Stability' }] },
    ],
  },
  {
    id: 'physics2', title: 'University Physics Vol. 2', sub: 'Ling · Sanny · Moebs', color: '#1a4dbf',
    bookTitle: 'University Physics Volume 2',
    chapters: [
      { n: '03', unit: 1, name: 'The First Law of Thermodynamics', secs: [{ n: '3.1', t: 'Thermodynamic Systems' }, { n: '3.2', t: 'Work, Heat, and Internal Energy' }, { n: '3.3', t: 'First Law of Thermodynamics' }, { n: '3.4', t: 'Thermodynamic Processes' }, { n: '3.5', t: 'Heat Capacities of an Ideal Gas' }] },
      { n: '05', unit: 2, name: 'Electric Charges and Fields', secs: [{ n: '5.1', t: 'Electric Charge' }, { n: '5.2', t: 'Conductors, Insulators, and Charging by Induction' }, { n: '5.3', t: "Coulomb's Law" }, { n: '5.4', t: 'Electric Field' }, { n: '5.5', t: 'Calculating Electric Fields of Charge Distributions' }] },
      { n: '10', unit: 2, name: 'Direct-Current Circuits', secs: [{ n: '10.1', t: 'Electromotive Force' }, { n: '10.2', t: 'Resistors in Series and Parallel' }, { n: '10.3', t: "Kirchhoff's Rules" }, { n: '10.4', t: 'Electrical Measuring Instruments' }, { n: '10.5', t: 'RC Circuits' }] },
    ],
  },
  {
    id: 'astronomy', title: 'Astronomy 2e', sub: 'Fraknoi · Morrison · Wolff', color: '#1565c0',
    bookTitle: 'Astronomy 2e',
    chapters: [
      { n: '01', unit: 1, name: 'Science and the Universe: A Brief Tour', secs: [{ n: '1.1', t: 'The Nature of Astronomy' }, { n: '1.2', t: 'The Nature of Science' }, { n: '1.3', t: 'The Astronomical Perspective' }] },
      { n: '04', unit: 1, name: 'Earth, Moon, and Sky', secs: [{ n: '4.1', t: 'Earth and Sky' }, { n: '4.2', t: 'The Seasons' }, { n: '4.3', t: 'Keeping Time' }, { n: '4.5', t: 'Phases and Motions of the Moon' }] },
      { n: '15', unit: 3, name: 'The Sun: A Garden-Variety Star', secs: [{ n: '15.1', t: 'The Structure and Composition of the Sun' }, { n: '15.2', t: 'The Solar Cycle' }, { n: '15.3', t: 'Solar Activity above the Photosphere' }, { n: '15.4', t: 'Space Weather' }] },
    ],
  },

  // ─── Mathematics ───
  {
    id: 'precalc', title: 'Precalculus 2e', sub: 'Abramson', color: '#16a085',
    bookTitle: 'Precalculus 2e',
    chapters: [
      { n: '01', unit: 1, name: 'Functions', secs: [{ n: '1.1', t: 'Functions and Function Notation' }, { n: '1.2', t: 'Domain and Range' }, { n: '1.3', t: 'Rates of Change and Behavior of Graphs' }, { n: '1.4', t: 'Composition of Functions' }, { n: '1.5', t: 'Transformation of Functions' }, { n: '1.7', t: 'Inverse Functions' }] },
      { n: '05', unit: 2, name: 'Trigonometric Functions', secs: [{ n: '5.1', t: 'Angles' }, { n: '5.2', t: 'Unit Circle: Sine and Cosine Functions' }, { n: '5.3', t: 'The Other Trigonometric Functions' }, { n: '5.4', t: 'Right Triangle Trigonometry' }] },
    ],
  },
  {
    id: 'calc1', title: 'Calculus Volume 1', sub: 'Strang · Herman', color: '#2c3e50',
    bookTitle: 'Calculus Volume 1',
    chapters: [
      { n: '02', unit: 1, name: 'Limits', secs: [{ n: '2.1', t: 'A Preview of Calculus' }, { n: '2.2', t: 'The Limit of a Function' }, { n: '2.3', t: 'The Limit Laws' }, { n: '2.4', t: 'Continuity' }, { n: '2.5', t: 'The Precise Definition of a Limit' }] },
      { n: '03', unit: 1, name: 'Derivatives', secs: [{ n: '3.1', t: 'Defining the Derivative' }, { n: '3.2', t: 'The Derivative as a Function' }, { n: '3.3', t: 'Differentiation Rules' }, { n: '3.4', t: 'Derivatives as Rates of Change' }, { n: '3.5', t: 'Derivatives of Trigonometric Functions' }, { n: '3.6', t: 'The Chain Rule' }] },
      { n: '05', unit: 2, name: 'Integration', secs: [{ n: '5.1', t: 'Approximating Areas' }, { n: '5.2', t: 'The Definite Integral' }, { n: '5.3', t: 'The Fundamental Theorem of Calculus' }, { n: '5.4', t: 'Integration Formulas and the Net Change Theorem' }, { n: '5.5', t: 'Substitution' }] },
    ],
  },
  {
    id: 'stats', title: 'Introductory Statistics 2e', sub: 'OpenStax', color: '#c0392b',
    bookTitle: 'Introductory Statistics 2e',
    chapters: [
      { n: '01', unit: 1, name: 'Sampling and Data', secs: [{ n: '1.1', t: 'Definitions of Statistics, Probability, and Key Terms' }, { n: '1.2', t: 'Data, Sampling, and Variation in Data and Sampling' }, { n: '1.3', t: 'Frequency, Frequency Tables, and Levels of Measurement' }, { n: '1.4', t: 'Experimental Design and Ethics' }] },
      { n: '07', unit: 3, name: 'The Central Limit Theorem', secs: [{ n: '7.1', t: 'The Central Limit Theorem for Sample Means (Averages)' }, { n: '7.2', t: 'The Central Limit Theorem for Sums' }, { n: '7.3', t: 'Using the Central Limit Theorem' }] },
    ],
  },

  // ─── Social Sciences ───
  {
    id: 'psych2e', title: 'Psychology 2e', sub: 'Spielman · Jenkins · Lovett', color: '#5e6a71',
    bookTitle: 'Psychology 2e',
    chapters: [
      { n: '03', unit: 1, name: 'Biopsychology', secs: [{ n: '3.1', t: 'Human Genetics' }, { n: '3.2', t: 'Cells of the Nervous System' }, { n: '3.3', t: 'Parts of the Nervous System' }, { n: '3.4', t: 'The Brain and Spinal Cord' }, { n: '3.5', t: 'The Endocrine System' }] },
      { n: '06', unit: 2, name: 'Learning', secs: [{ n: '6.1', t: 'What Is Learning?' }, { n: '6.2', t: 'Classical Conditioning' }, { n: '6.3', t: 'Operant Conditioning' }, { n: '6.4', t: 'Observational Learning (Modeling)' }] },
      { n: '08', unit: 3, name: 'Memory', secs: [{ n: '8.1', t: 'How Memory Functions' }, { n: '8.2', t: 'Parts of the Brain Involved with Memory' }, { n: '8.3', t: 'Problems with Memory' }, { n: '8.4', t: 'Ways to Enhance Memory' }] },
    ],
  },
  {
    id: 'sociology', title: 'Introduction to Sociology 3e', sub: 'Conerly · Holmes · Tamang', color: '#8e44ad',
    bookTitle: 'Introduction to Sociology 3e',
    chapters: [
      { n: '01', unit: 1, name: 'An Introduction to Sociology', secs: [{ n: '1.1', t: 'What Is Sociology?' }, { n: '1.2', t: 'The History of Sociology' }, { n: '1.3', t: 'Theoretical Perspectives in Sociology' }, { n: '1.4', t: 'Why Study Sociology?' }] },
      { n: '05', unit: 2, name: 'Socialization', secs: [{ n: '5.1', t: 'Theories of Self-Development' }, { n: '5.2', t: 'Why Socialization Matters' }, { n: '5.3', t: 'Agents of Socialization' }, { n: '5.4', t: 'Socialization Across the Life Course' }] },
    ],
  },

  // ─── Economics ───
  {
    id: 'micro', title: 'Principles of Microeconomics 3e', sub: 'Greenlaw · Shapiro', color: '#f4c61f',
    bookTitle: 'Principles of Microeconomics 3e',
    chapters: [
      { n: '01', unit: 1, name: 'Welcome to Economics!', secs: [{ n: '1.1', t: 'What Is Economics, and Why Is It Important?' }, { n: '1.2', t: 'Microeconomics and Macroeconomics' }, { n: '1.3', t: 'How Economists Use Theories and Models' }, { n: '1.4', t: 'How To Organize Economies: An Overview of Economic Systems' }] },
      { n: '03', unit: 1, name: 'Demand and Supply', secs: [{ n: '3.1', t: 'Demand, Supply, and Equilibrium in Markets for Goods and Services' }, { n: '3.2', t: 'Shifts in Demand and Supply for Goods and Services' }, { n: '3.3', t: 'Changes in Equilibrium Price and Quantity: The Four-Step Process' }, { n: '3.4', t: 'Price Ceilings and Price Floors' }] },
    ],
  },
  {
    id: 'macro', title: 'Principles of Macroeconomics 3e', sub: 'Greenlaw · Shapiro', color: '#e67e22',
    bookTitle: 'Principles of Macroeconomics 3e',
    chapters: [
      { n: '06', unit: 2, name: 'The Macroeconomic Perspective', secs: [{ n: '6.1', t: 'Measuring the Size of the Economy: Gross Domestic Product' }, { n: '6.2', t: 'Adjusting Nominal Values to Real Values' }, { n: '6.3', t: 'Tracking Real GDP over Time' }, { n: '6.4', t: 'Comparing GDP among Countries' }, { n: '6.5', t: 'How Well GDP Measures the Well-Being of Society' }] },
      { n: '10', unit: 3, name: 'The Aggregate Demand/Aggregate Supply Model', secs: [{ n: '10.1', t: 'Macroeconomic Perspectives on Demand and Supply' }, { n: '10.2', t: 'Building a Model of Aggregate Demand and Aggregate Supply' }, { n: '10.3', t: 'Shifts in Aggregate Supply' }, { n: '10.4', t: 'Shifts in Aggregate Demand' }, { n: '10.5', t: 'How the AD/AS Model Incorporates Growth, Unemployment, and Inflation' }] },
    ],
  },
  {
    id: 'introbiz', title: 'Introduction to Business', sub: 'Gitman · McDaniel', color: '#7f8c8d',
    bookTitle: 'Introduction to Business',
    chapters: [
      { n: '01', unit: 1, name: 'Understanding Economic Systems and Business', secs: [{ n: '1.1', t: 'The Nature of Business' }, { n: '1.2', t: 'Understanding the Business Environment' }, { n: '1.3', t: 'How Business and Economics Work' }, { n: '1.4', t: 'Macroeconomics: The Big Picture' }, { n: '1.5', t: 'Achieving Macroeconomic Goals' }] },
      { n: '06', unit: 2, name: 'Management and Leadership in Today\'s Organizations', secs: [{ n: '6.1', t: 'The Role of Management' }, { n: '6.2', t: 'Planning' }, { n: '6.3', t: 'Organizing' }, { n: '6.4', t: 'Leading, Guiding, and Motivating Others' }, { n: '6.5', t: 'Controlling' }] },
    ],
  },
];

// ── Utility functions ──────────────────────────────────────────────────────

interface LookupResult {
  book: CatalogBook;
  chap: CatalogChapter;
  secN: string;
}

export function lookupSection(id: string): LookupResult | null {
  const [bookId, chapN, secN] = id.split(':');
  const book = CATALOG.find(b => b.id === bookId);
  if (!book) return null;
  const chap = book.chapters.find(c => c.n === chapN);
  if (!chap) return null;
  return { book, chap, secN };
}

interface BuildRequestParams {
  selected: Set<string>;
  model: ModelChoice;
  videoType: VideoType;
  userQuery: string;
}

export function buildGenerateRequest({
  selected,
  model,
  videoType,
  userQuery,
}: BuildRequestParams): GenerateRequest | null {
  const firstId = Array.from(selected)[0];
  const hit = firstId ? lookupSection(firstId) : null;
  if (!hit) return null;
  return {
    book_title: hit.book.bookTitle,
    unit_num: hit.chap.unit ?? null,
    chapter_num: parseInt(hit.chap.n, 10),
    page_num: hit.secN,
    user_query: userQuery,
    model_choice: model,
    video_type: videoType,
  };
}
