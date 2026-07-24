-- LCAI-0010B acceptance fix: additive primary and collège reference levels.

INSERT INTO school_levels(id,code,label,rank,country_code) VALUES
    (15,'FR-CM1','CM1',8,'FR'),
    (16,'FR-CM2','CM2',7,'FR'),
    (17,'FR-6E','Sixième',6,'FR'),
    (18,'FR-5E','Cinquième',5,'FR');

ALTER TABLE learner_experience_profiles ADD COLUMN email VARCHAR;
