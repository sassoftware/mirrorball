    def cook(self, group):
        """
        Go through all the packages in a group that's on the current label and cook them.
        """

        self.repo()
        from conary import display, queryrep, trove

        troveTups = queryrep.getTrovesToDisplay(
            self.repos, [group], [],
            versionFilter=queryrep.VERSION_FILTER_LATEST,
            flavorFilter=queryrep.FLAVOR_FILTER_BEST,
            labelPath=self.cfg.buildLabel, defaultFlavor=self.cfg.flavor,
            affinityDb=None)

        dcfg = display.DisplayConfig(self.repos, None)
        troveSource = dcfg.getTroveSource()
        troves = troveSource.getTroves(troveTups, withFiles=False)
        childTups = list(troves[0].iterTroveList(strongRefs=True))

        import epdb
        epdb.st()

        troveSpecs = [(group, None, None)]
        self.repos.findTroves(self.cfg.buildLabel, troveSpecs)

        troveTups = [(group, None, None)]

        #t = troveSource.getTroves(troveTups)
        ttup = self.repos.findTroves(self.cfg.buildLabel, troveTups)[troveTups[0]]


