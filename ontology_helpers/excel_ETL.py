import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, XSD
from datetime import datetime
import re

# Define namespaces
MEAS = Namespace("http://example.org/ontology/teamMeasurement#")
EVID = Namespace("http://example.org/ontology/evidence#")
LINK = Namespace("http://example.org/ontology/linking#")
INST = Namespace("http://example.org/ontology/instances#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# In __init__, add:


class ExcelToOntologyMapper:
    def __init__(self, excel_path, ontology_dir='.', append_to_existing=False):
        self.excel_path = excel_path
        self.ontology_dir = ontology_dir
        self.append_to_existing = append_to_existing
        self.graph = Graph()
        
        # Bind namespaces
        self.graph.bind("meas", MEAS)
        self.graph.bind("evid", EVID)
        self.graph.bind("link", LINK)
        self.graph.bind("inst", INST)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)
        
        # Load existing ontologies
        self.load_ontologies()
        
        # Load Excel data
        self.publications_df = pd.read_excel(excel_path, sheet_name='publications')
        self.studies_df = pd.read_excel(excel_path, sheet_name='studies')
        self.measures_df = pd.read_excel(excel_path, sheet_name='measures')
        self.effects_df = pd.read_excel(excel_path, sheet_name='effects')
        
    def load_ontologies(self):
        """Load the base ontology definitions"""
        ontology_files = [
            'teamMeasurement.ttl',
            'evidence.ttl',
            'instances.ttl'  # if you want to append to existing instances
        ]
        
        for file in ontology_files:
            try:
                self.graph.parse(file, format='turtle')
                print(f"Loaded {file}")
            except Exception as e:
                print(f"Error loading {file}: {e}")
    
    def clean_uri_string(self, text):
        """Clean text for use in URIs"""
        if pd.isna(text):
            return ""
        # Remove special characters and spaces
        cleaned = re.sub(r'[^a-zA-Z0-9_-]', '_', str(text))
        # Remove multiple underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        return cleaned.strip('_')
    
    def map_publications(self):
        """Map publications tab to ontology instances"""
        for _, row in self.publications_df.iterrows():
            pub_uri = INST[row['publication_id']]
            
            # Add type assertion
            self.graph.add((pub_uri, RDF.type, EVID.Publication))
            
            # Add properties
            if pd.notna(row.get('DOI')):
                self.graph.add((pub_uri, EVID.hasDOI, Literal(row['DOI'], datatype=XSD.string)))
            
            if pd.notna(row.get('pubYear')):
                self.graph.add((pub_uri, EVID.hasPubYear, Literal(str(row['pubYear']), datatype=XSD.string)))
            
            if pd.notna(row.get('firstAuthor')):
                self.graph.add((pub_uri, EVID.hasFirstAuthor, Literal(row['firstAuthor'], datatype=XSD.string)))
    
    def map_studies(self):
        """Map studies tab to ontology instances"""
        for _, row in self.studies_df.iterrows():
            study_uri = INST[row['study_id']]
            pub_uri = INST[row['publication_id']]
            
            # Add type assertion
            study_type = row.get('studyType')
            if study_type == 'primary':
                self.graph.add((study_uri, RDF.type, EVID.primaryStudy))
            elif study_type == 'meta-analysis':
                self.graph.add((study_uri, RDF.type, EVID.metaAnalysis))
            
            # Link to publication
            self.graph.add((pub_uri, EVID.reportsStudy, study_uri))
            
            # Add properties
            if pd.notna(row.get('hasStudyPopulation')):
                self.graph.add((study_uri, EVID.hasStudyPopulation, Literal(f"Study Population: {row['hasStudyPopulation']}")))
            # Need to finish adding these
            # if pd.notna(row.get('teamSize')):
            #     self.graph.add((study_uri, MEAS.hasTeamSize, Literal(row['teamSize'], datatype=XSD.integer)))
    
    def map_modality(self, modality_text):
        """Map modality text to ontology classes"""
        modality_mapping = {
            'communication content': MEAS.communicationContent,
            'communication flow': MEAS.communication,
            'survey': MEAS.survey,
            'behavior': MEAS.behavior,
            'physiology': MEAS.physiology,
            'task outcome': MEAS.behavior,  # Assuming task outcome is a type of behavior
        }
        
        if pd.isna(modality_text):
            return None
        
        modality_lower = modality_text.lower().strip()
        return modality_mapping.get(modality_lower, None)
    
    def map_construct(self, construct_text):
        """Map construct text to ontology construct classes"""
        if pd.isna(construct_text):
            return None
        
        construct_lower = str(construct_text).lower()
        
        construct_map = {
            'team performance': MEAS.teamPerformance,
            'performance': MEAS.teamPerformance,
            'cohesion': MEAS.cohesion,
            'team cohesion': MEAS.cohesion,
            'cognitive load': MEAS.cognitiveLoad,
            'cognition': MEAS.cognition,
            'satisfaction': MEAS.satisfaction,
            'shared mental model': MEAS.sharedMentalModel,
            'situational awareness': MEAS.situationalAwareness,
            'problem solving': MEAS.problemSolving,
            'resilience': MEAS.resilience,
            'stress': MEAS.stress,
            'team familiarity': MEAS.teamFamiliarity,
            'team size': MEAS.teamSize,
            'task type': MEAS.taskType
        }
        
        for key, value in construct_map.items():
            if key in construct_lower:
                return value
        
        return None
    
    def map_analytic_technique(self, technique_text):
        """Map analytic technique to ontology classes"""
        technique_mapping = {
            'mean': MEAS.simpleAggregation,
            'average': MEAS.simpleAggregation,
            'cosine similarity': MEAS.synchrony,
            'mutual information': MEAS.informationTheoretic,
            'average mutual information': MEAS.informationTheoretic,
            'normalized shannon entropy': MEAS.informationTheoretic,
            'network analysis': MEAS.networkAnalysis,
            'crqa': MEAS.CRQA,
        }
        
        if pd.isna(technique_text):
            return None
            
        technique_lower = technique_text.lower().strip()
        
        # Check for partial matches
        for key, value in technique_mapping.items():
            if key in technique_lower:
                return value
        
        return None
    def map_method(self, method_text):
        """Map method text to ontology method classes"""
        if pd.isna(method_text):
            return None
        
        method_lower = str(method_text).lower()
        
        method_map = {
            'synchrony': MEAS.synchrony,
            'information theoretic': MEAS.informationTheoretic,
            'simple aggregation': MEAS.simpleAggregation,
            'aggregation': MEAS.simpleAggregation,
            'network analysis': MEAS.networkAnalysis,
            'crqa': MEAS.CRQA
        }
        
        for key, value in method_map.items():
            if key in method_lower:
                return value
        
        return None

    def map_measures(self):
        """Map measures tab to ontology instances"""
        for _, row in self.measures_df.iterrows():
            measure_uri = INST[row['measure_id']]
            
            # Add type assertion
            self.graph.add((measure_uri, RDF.type, MEAS.Measure))
            
            # Add properties
            if pd.notna(row.get('name')):
                self.graph.add((measure_uri, MEAS.hasName, 
                            Literal(row['name'], datatype=XSD.string)))
            
            # Add label and description
            if pd.notna(row.get('hasName')):
                self.graph.add((measure_uri, MEAS.hasName, Literal(row['hasName'])))
            
            if pd.notna(row.get('hasDescription')):
                self.graph.add((measure_uri, MEAS.hasDescription, Literal(row['hasDescription'])))
            
            # Map modality
            modality_class = self.map_modality(row.get('includesModality'))
            if modality_class:
                self.graph.add((measure_uri, MEAS.includesModality, modality_class))
            
            # Map construct
            construct_class = self.map_construct(row.get('construct'))
            if construct_class:
                self.graph.add((measure_uri, MEAS.measuresConstruct, construct_class))
            
            # Map analytic technique
            if pd.notna(row.get('usesAnalyticTechnique')):
                technique_class = self.map_analytic_technique(row['usesAnalyticTechnique'])
                if technique_class:
                    # Create method instance
                    method_uri = INST[f"{row['measure_id']}_method"]
                    self.graph.add((method_uri, RDF.type, technique_class))
                    self.graph.add((measure_uri, MEAS.usesMethod, method_uri))
            
            # Map level of analysis
            if pd.notna(row.get('hasLevelOfAnalysis')):
                level = row['hasLevelOfAnalysis'].lower().strip()
                if level == 'team':
                    self.graph.add((measure_uri, MEAS.hasLevelOfAnalysis, MEAS.team))
                elif level == 'individual':
                    self.graph.add((measure_uri, MEAS.hasLevelOfAnalysis, MEAS.individual))
                elif level == 'dyad':
                    self.graph.add((measure_uri, MEAS.hasLevelOfAnalysis, MEAS.dyad))
                elif level == 'cross-level':
                    self.graph.add((measure_uri, MEAS.hasLevelOfAnalysis, MEAS.crossLevel))
            # Map and add method if present
            if pd.notna(row.get('method')):
                method_class = self.map_method(row['method'])
                if method_class:
                    # Create a method instance
                    method_uri = INST[f"{row['measure_id']}_method"]
                    self.graph.add((method_uri, RDF.type, method_class))
                    self.graph.add((measure_uri, MEAS.usesMethod, method_uri))
            # add interpretation
            if pd.notna(row.get('hasInterpretation')):
                self.graph.add((measure_uri, MEAS.hasInterpretation, Literal(row['hasInterpretation'])))
            # add interpretation
            if pd.notna(row.get('hasScale')):
                self.graph.add((measure_uri, MEAS.hasScale, Literal(row['hasScale'])))
    def validate_excel_structure(self):
        """Validate that Excel file has required sheets and columns"""
        required_sheets = ['publications', 'studies', 'measures', 'effects']
        required_columns = {
            'publications': ['publication_id', 'DOI', 'pubYear', 'firstAuthor'],
            'studies': ['study_id', 'publication_id', 'studyType'],
            'measures': ['measure_id', 'name', 'modality', 'construct'],
            'effects': ['effect_id', 'study_id', 'independentVariable', 'dependentVariable']
        }
        
        # Check sheets exist
        excel_file = pd.ExcelFile(self.excel_path)
        for sheet in required_sheets:
            if sheet not in excel_file.sheet_names:
                raise ValueError(f"Missing required sheet: {sheet}")
        
        # Check columns exist
        for sheet, columns in required_columns.items():
            df = pd.read_excel(self.excel_path, sheet_name=sheet)
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                print(f"Warning: Missing columns in {sheet}: {missing_cols}")
    def map_effects(self):
        """Map effects tab to ontology instances"""
        for idx, row in self.effects_df.iterrows():
            try:
                # Create effect size instance
                effect_uri = INST[f"effect_{row['effect_id']}"]
                study_uri = INST[row['study_id']]
                
                # Add type assertion
                self.graph.add((effect_uri, RDF.type, EVID.EffectSize))
                
                # Link to study
                self.graph.add((study_uri, EVID.reportsEffectSize, effect_uri))
                
                # Add measures
                if pd.notna(row.get('indepdentVariable')):
                    measure1_uri = INST[row['indepdentVariable']]
                    self.graph.add((effect_uri, EVID.hasIndependentVariable, measure1_uri))
                
                if pd.notna(row.get('dependentVariable')):
                    measure2_uri = INST[row['dependentVariable']]
                    self.graph.add((effect_uri, EVID.hasDependentVariable, measure2_uri))
                
                # Add effect size properties
                if pd.notna(row.get('hasEffectSizeValue')):
                    self.graph.add((effect_uri, EVID.hasEffectSizeValue, 
                                Literal(float(row['hasEffectSizeValue']), datatype=XSD.float)))
                
                if pd.notna(row.get('usesEffectSizeMetric')):
                    self.graph.add((effect_uri, EVID.usesEffectSizeMetric, 
                                Literal(row['usesEffectSizeMetric'], datatype=XSD.string)))
                
                if pd.notna(row.get('hasPValue')):
                    self.graph.add((effect_uri, EVID.hasPValue, 
                                Literal(float(row['hasPValue']), datatype=XSD.float)))
                
                if pd.notna(row.get('hasLowerCI')):
                    self.graph.add((effect_uri, EVID.hasLowerCI, 
                                Literal(float(row['hasLowerCI']), datatype=XSD.float)))
                
                if pd.notna(row.get('hasUpperCI')):
                    self.graph.add((effect_uri, EVID.hasUpperCI, 
                                Literal(float(row['hasUpperCI']), datatype=XSD.float)))
                
                # Add sample sizes
                if pd.notna(row.get('individualSampleSize')):
                    self.graph.add((effect_uri, EVID.hasIndividualSampleSize, 
                                Literal(int(row['individualSampleSize']), datatype=XSD.integer)))
                
                if pd.notna(row.get('teamSampleSize')):
                    self.graph.add((effect_uri, EVID.hasTeamSampleSize, 
                                Literal(int(row['teamSampleSize']), datatype=XSD.integer)))
            except Exception as e:
                print(f"Error processing effect row {idx}: {e}")
                continue
    def process_all(self):
        """Process all tabs and generate the complete ontology"""
        print("Processing publications...")
        self.map_publications()
        
        print("Processing studies...")
        self.map_studies()
        
        print("Processing measures...")
        self.map_measures()
        
        print("Processing effects...")
        self.map_effects()
        
        print(f"Total triples generated: {len(self.graph)}")
    
    def save_to_file(self, output_path):
        """Save the generated ontology to a Turtle file"""
        self.graph.serialize(destination=output_path, format='turtle')
        print(f"Ontology saved to: {output_path}")
    
    def validate_mappings(self):
        """Validate that all mappings were successful"""
        # Check for unmapped measures
        unmapped_modalities = []
        unmapped_constructs = []
        
        for _, row in self.measures_df.iterrows():
            if pd.notna(row.get('modality')) and not self.map_modality(row['modality']):
                unmapped_modalities.append(row['modality'])
            
            if pd.notna(row.get('construct')) and not self.map_construct(row['construct']):
                unmapped_constructs.append(row['construct'])
        
        if unmapped_modalities:
            print(f"Warning: Unmapped modalities: {set(unmapped_modalities)}")
        
        if unmapped_constructs:
            print(f"Warning: Unmapped constructs: {set(unmapped_constructs)}")

# Usage example
if __name__ == "__main__":
    # Initialize the mapper
    mapper = ExcelToOntologyMapper('ontology_coding_template.xlsx')
    
    # Process all data
    mapper.process_all()
    
    # Validate mappings
    mapper.validate_mappings()
    
    # Save to file
    mapper.save_to_file('instances_from_excel.ttl')
    
    # Optionally, print a sample of the generated RDF
    print("\nSample of generated RDF:")
    print(mapper.graph.serialize(format='turtle')[:1000])